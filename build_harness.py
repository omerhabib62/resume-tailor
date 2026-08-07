"""
build_harness.py — Resume Tailor target-pack for the PAI multi-agent build harness.

REUSES the PAI core (make_llm, schemas, write_file, run_shell, LangGraph shape) and swaps
the PAI SQL target-pack for a resume-tailoring one:
  - context  = AGENTS.md + rules/tailoring-rules.md + master-profile.yaml (the "data model")
  - prompts  = de-PAI'd (build Python resume-tailor artifacts, obey RT-* rules), NOT SQL migrations
  - exec gate = Python code-gate (py_compile + pytest)   [replaces sqlfluff + schema-diff]

RUN (from D:\\projects\\resume-tailor, venv active, .env with GEMINI_API_KEY or GROQ_API_KEY):
    python build_harness.py spec/tailor-spec.md
Set provider with:  LLM_PROVIDER=groq  (or gemini)
"""
from __future__ import annotations
import os, sys, json, yaml

# --- harness core is vendored locally in ./harness (self-contained, no external path needed) ---
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt, Command
from typing import TypedDict

from harness.llm import make_llm                       # provider registry (Groq/Gemini)
from harness.schemas import Plan, EngineerOutput, ReviewResult
from harness.tools import write_file, run_shell        # writes confined to CWD; allow-list has python/pytest

load_dotenv()
llm = make_llm()
planner      = llm.with_structured_output(Plan, method="json_mode")
coder        = llm.with_structured_output(EngineerOutput, method="json_mode")
reviewer_llm = llm.with_structured_output(ReviewResult, method="json_mode")

MAX_RETRIES = 3   # give the deterministic-gate + guidance loop room to self-correct before escalating
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------- context loaders (this target-pack) ----------------
def _read(rel: str) -> str:
    p = os.path.join(HERE, rel)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

def load_agents() -> str: return _read("AGENTS.md")
def load_rules() -> str:  return _read(os.path.join("rules", "tailoring-rules.md"))

def load_target_facts() -> str:
    """The 'data model' analog: master-profile shape + the gate contract the code must satisfy."""
    prof = _read("master-profile.yaml")
    gates = _read("gates.py")
    shape = "\n".join(l for l in prof.splitlines() if l and not l.startswith("#"))[:2500]
    gate_hdr = "\n".join(gates.splitlines()[:28])
    return f"MASTER-PROFILE SHAPE (source of truth):\n{shape}\n\nGATE CONTRACT (output must pass these):\n{gate_hdr}"


# ---------------- ARCHITECT ----------------
ARCHITECT_PROMPT = """ROLE
You are the Architect for the Resume Tailor. Decompose the SPEC into a minimal, ordered list of
discrete, buildable Python tasks. You do NOT write code. Respond in json.

READ FIRST
1. SPEC (below) - what to build.
2. TARGET FACTS (below) - the master-profile shape (source of truth) and the gate contract the code must satisfy.
3. AGENTS + RULES (below) - conventions and RT-* rules every task must respect.

PRODUCE - for each task: id, description, files, depends_on, acceptance.
`acceptance` MUST be complete and testable so the Engineer never re-derives anything:
  - exact file path(s) and what each function/module must do
  - inputs/outputs and data shapes
  - which RT-* rules it enforces and how (e.g. "runs gates.check_provenance; on fail, re-prompt")
  - the deterministic check that proves it (compiles; named pytest passes)

MUST NOT
- Do NOT write code. Do NOT leave a task partially specified. No "etc."/"...".
- Do NOT invent files or behaviour not in the SPEC.

UNCERTAINTY: ambiguous detail -> put "[NEEDS REVIEW: <question>]" in that task's acceptance. Never guess.

GATE (output rejected unless): every task has explicit file paths; full acceptance; correct depends_on order.

=== AGENTS ===
{agents}
=== RULES ===
{rules}
=== TARGET FACTS ===
{facts}
=== SPEC ===
{spec}

OUTPUT: ONLY json {{"tasks": [{{"id": "...","description": "...","files": ["..."],"depends_on": ["..."],"acceptance": "..."}}]}}
"""

def architect(spec_path: str) -> dict:
    spec = open(spec_path, encoding="utf-8").read()
    plan: Plan = planner.invoke(ARCHITECT_PROMPT.format(
        agents=load_agents(), rules=load_rules(), facts=load_target_facts(), spec=spec))
    return plan.model_dump()


# ---------------- ENGINEER ----------------
ENGINEER_PROMPT = """ROLE
You are the Engineer for the Resume Tailor. Implement EXACTLY ONE task by returning complete file
contents. Respond in json.

READ FIRST
1. TASK - its `acceptance` is the COMPLETE spec. Implement all of it.
2. AGENTS + RULES - conventions and RT-* rules. Non-negotiable. Truth first: never fabricate.
3. CURRENT FILE CONTENT (if present) - the file EXISTS. EDIT it; do NOT regenerate from scratch.
4. FIX LIST (if present) - a check or reviewer failed. Fix exactly these, change nothing else.

MUST
- Return the COMPLETE updated file(s) - never a diff, never a fragment. No omissions, no "...".
- Write clean Python. If the task says to enforce an RT-* rule via gates.py, import and call it.
- PRESERVE every already-correct part not mentioned in the fix list.

MUST NOT
- No extra files, functions, or behaviour beyond the acceptance.
- Never invent a candidate skill/metric - that is the tailorer's cardinal sin (RT-TRUTH-001/002).

UNCERTAINTY: missing detail -> a `# [NEEDS REVIEW: <what>]` comment above the line. Never invent a value.

=== AGENTS ===
{agents}
=== RULES ===
{rules}
=== TASK ===
{task}
{fixes}{existing}

OUTPUT: ONLY json {{"files": [{{"path": "<repo-relative path>", "content": "<full file content>"}}], "notes": ""}}
"""

class State(TypedDict):
    task: dict
    code: str
    review: dict
    retries: int
    approved: bool
    files_written: list
    test_output: str
    test_passed: bool

def engineer(state: State) -> dict:
    fixes = ""
    if state.get("review") and not state["review"]["passed"]:
        fixes += "\n=== FIX LIST (reviewer) ===\n" + str(state["review"].get("fix_instructions", "")) + "\n"
    if state.get("test_passed") is False and state.get("test_output"):
        fixes += "\n=== FIX LIST (automated checks FAILED - fix exactly these) ===\n" + state["test_output"] + "\n"

    existing = ""
    for p in state.get("task", {}).get("files", []) or []:
        if os.path.exists(p):
            try:
                existing += f"\n=== CURRENT FILE CONTENT: {p} ===\n" + open(p, encoding="utf-8").read() + "\n"
            except Exception:
                pass
    if existing:
        existing = ("\n(The file(s) below ALREADY EXIST. Return the COMPLETE updated file, applying ONLY "
                    "the requested fixes and PRESERVING everything else that is correct.)\n" + existing)

    out: EngineerOutput = coder.invoke(ENGINEER_PROMPT.format(
        agents=load_agents(), rules=load_rules(),
        task=json.dumps(state["task"], indent=2), fixes=fixes, existing=existing))
    written = []
    for fe in out.files:
        write_file(fe.path, fe.content)
        written.append(fe.path)
    return {"code": "\n\n".join(f"# {fe.path}\n{fe.content}" for fe in out.files), "files_written": written}


# ---------------- EXECUTION (deterministic, no LLM) ----------------
def code_gate(files: list[str]) -> dict:
    py = [p for p in (files or []) if p.endswith(".py")]
    if not py:
        return {"ok": True, "output": "no .py files to check"}
    errs = []
    for p in py:
        r = run_shell(f'python -m py_compile "{p}"')
        if not r["ok"]:
            errs.append(f"--- compile {p} ---\n{r['output'][:1500]}")
    tests = [p for p in py if os.path.basename(p).startswith("test_") or p.endswith("_test.py")]
    if not errs and tests:
        r = run_shell("python -m pytest -q " + " ".join(f'"{t}"' for t in tests))
        if not r["ok"]:
            errs.append("PYTEST FAILED:\n" + r["output"][:1500])
    ok_msg = "code compiles" + (" + tests pass" if tests else " (no tests in task)")
    return {"ok": not errs, "output": "\n".join(errs) if errs else ok_msg}

def load_checks() -> dict:
    p = os.path.join(HERE, "spec", "checks.yaml")
    return yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else {}

def content_gate(files: list[str]) -> dict:        # deterministic content contract, NO LLM
    checks = load_checks()
    errs, guides = [], []
    for path in files or []:
        spec = checks.get(os.path.basename(path))
        if not spec or not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        file_errs = []
        for tok in spec.get("must_contain") or []:
            if tok not in text:
                file_errs.append(f"{os.path.basename(path)}: MUST contain '{tok}' — it is missing")
        for tok in spec.get("must_not_contain") or []:
            if tok in text:
                file_errs.append(f"{os.path.basename(path)}: must NOT contain '{tok}' — it is present")
        if file_errs and spec.get("guidance"):      # hand the engineer the HOW, so it self-corrects
            guides.append(f"HOW TO FIX {os.path.basename(path)}: {spec['guidance'].strip()}")
        errs += file_errs
    if not errs:
        return {"ok": True, "output": "content contract OK"}
    out = "CONTENT CONTRACT FAILED (fix exactly these):\n- " + "\n- ".join(errs)
    if guides:
        out += "\n\n" + "\n".join(guides)
    return {"ok": False, "output": out}

def execution(state: State) -> dict:
    files = state.get("files_written", [])
    res = code_gate(files)                          # 1) compiles + any tests pass?
    if res["ok"]:
        c = content_gate(files)                     # 2) meets the human-authored content contract?
        res = c if not c["ok"] else {"ok": True, "output": res["output"] + " | " + c["output"]}
    out = {"test_output": res["output"], "test_passed": res["ok"]}
    if not res["ok"]:
        out["retries"] = state.get("retries", 0) + 1
    return out

def route_exec(state: State) -> str:
    if state.get("test_passed"):
        return "review"
    return "gate" if state.get("retries", 0) >= MAX_RETRIES else "retry"


# ---------------- REVIEWER ----------------
REVIEWER_PROMPT = """ROLE
You are a STRICT QA reviewer for the Resume Tailor. Verify CODE against the TASK acceptance and the
RT-* RULES. You are adversarial. Partial compliance is a FAIL. Respond in json.

CHECKLIST - satisfied ONLY if FULLY satisfied
A. Completeness - every function/behaviour in the acceptance is present; nothing extra.
B. Truth enforcement - any tailoring logic must obey RT-TRUTH-001/002: only facts from master-profile;
   fabricated skills/metrics impossible. If the task enforces a rule via gates.py, it actually calls it.
C. Fidelity - docx handling edits text runs only; never regenerates/ restyles (RT-FORMAT-001).
D. Robustness - inputs validated; errors handled; no crash on missing/edge input.
E. Rules - no RT-* rule violated. Name any rule ID that is.

GRADING: passed=true ONLY if A-E fully hold. Otherwise passed=false and list each failure as a
SPECIFIC issue (name the exact function/line and the RT-* rule ID where one applies).

MUST NOT: pass code with any unsatisfied item; suggest out-of-scope improvements; rewrite the code.

=== RULES ===
{rules}
=== TASK ===
{task}
=== CODE ===
{code}

OUTPUT: ONLY json {{"passed": true/false, "issues": ["..."], "fix_instructions": "..."}}
"""

def reviewer(state: State) -> dict:
    review: ReviewResult = reviewer_llm.invoke(REVIEWER_PROMPT.format(
        rules=load_rules(), task=json.dumps(state["task"]), code=state["code"]))
    return {"review": review.model_dump(), "retries": state.get("retries", 0) + 1}

def human_gate(state: State) -> dict:
    r = state.get("review", {})
    status = "Review PASSED" if r.get("passed") else f"Review FAILED after retries — issues: {r.get('issues')}"
    if state.get("test_passed") is False:
        status += "\nAUTOMATED CHECKS FAILED:\n" + str(state.get("test_output", ""))[:800]
    decision = interrupt({"summary": f"{status}. Approve? ('approve' or type fix notes)", "code": state["code"]})
    if str(decision).strip().lower() == "approve":
        return {"approved": True}
    return {"approved": False,
            "review": {"passed": False, "issues": ["human rejected"], "fix_instructions": str(decision)}}

def route_review(state: State) -> str:
    if state["review"]["passed"]:
        return "gate"
    return "give_up" if state["retries"] >= MAX_RETRIES else "retry"

def route_gate(state: State) -> str:
    return "done" if state.get("approved") else "retry"


# ---------------- graph ----------------
_b = StateGraph(State)
_b.add_node("engineer", engineer)
_b.add_node("execution", execution)
_b.add_node("reviewer", reviewer)
_b.add_node("human_gate", human_gate)
_b.add_edge(START, "engineer")
_b.add_edge("engineer", "execution")
_b.add_conditional_edges("execution", route_exec, {"review": "reviewer", "retry": "engineer", "gate": "human_gate"})
_b.add_conditional_edges("reviewer", route_review, {"retry": "engineer", "gate": "human_gate", "give_up": "human_gate"})
_b.add_conditional_edges("human_gate", route_gate, {"retry": "engineer", "done": END})
loop_graph = _b.compile(checkpointer=MemorySaver())


def build(spec_path: str):
    print(f"\n=== ARCHITECT: {spec_path} ===")
    plan = architect(spec_path)
    print(f"Plan: {len(plan['tasks'])} task(s)")
    for task in plan["tasks"]:
        print(f"\n--- {task['id']}: {task['description']} ---")
        cfg = {"configurable": {"thread_id": f"{os.path.basename(spec_path)}-{task['id']}"}}
        result = loop_graph.invoke({"task": task, "retries": 0}, cfg)
        while "__interrupt__" in result:
            p = result["__interrupt__"][0].value
            print("\n--- HUMAN GATE ---"); print(p["summary"]); print(p["code"][:2000])
            result = loop_graph.invoke(Command(resume=input("\n> ")), cfg)
        if not result.get("approved"):
            print(f"{task['id']} rejected — aborting build."); return
    print("\n=== BUILD COMPLETE ===")


if __name__ == "__main__":
    spec = sys.argv[1] if len(sys.argv) > 1 else "spec/tailor-spec.md"
    build(spec)
