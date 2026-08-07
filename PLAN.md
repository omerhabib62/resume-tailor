# Resume Tailor — Build Plan & Progress

A **new target-pack for the PAI multi-agent build harness** (`D:\projects\PAI\harness`).
Reuses the harness core (LangGraph graph, `llm.py`, human_gate, watchdog, schemas); swaps the
PAI SQL target-pack for a resume-tailoring one. Doing this cleanly turns the harness from a
one-off PAI builder into a genuine **multi-target** build harness.

Newest first. One line per decision or artifact.

## What we're building (the runtime product)
- **Input:** a job post + `master-profile.yaml` (single source of truth).
- **Process:** LLM tailors ONLY from the master (title, summary, keyword line, selected/reworded bullets).
- **Output:** targeted edits into a COPY of the master Word `.docx` (preserves exact design — the
  proven docx-XML-edit technique) → `applied/<company>/` (+ optional PDF).
- **n8n:** added LAST as an optional front-door/trigger — not the core.

## Architecture decisions (locked)
- **D0** Substrate = extend existing PAI LangGraph harness (Groq/Gemini). Most reuse; revives paused work.
- **D1** Output = **Word-fidelity** (keep Omer's existing `.docx` design; edit text runs in place).
  Ruled out Google-Docs rebuild (design drift) — Omer already has the Word format.
- **D2** Truth model = `master-profile.yaml` is the ONLY source; tailorer selects/reframes, never invents.
- **D3** Format = YAML (readable + machine-parseable; maps 1:1 to JSON for a future editing UI).
- **D4** Schema v2 validated against real resumes (Golden Gate AI + BI Analyst): added project
  `highlights[]` + `case_study`, open `skills` map, `positioning.strengths[]`.

## Deterministic gates (replace PAI's sqlfluff + schema-diff)
- **G1 Provenance:** every skill/tool/metric token in tailored output must trace to `master-profile.yaml`. Fail → engineer.
- **G2 No leftover placeholders:** output `.docx` has no `{{...}}` / unfilled markers.
- **G3 Section integrity:** required resume sections all present; nothing silently dropped.
- **G4 Docx-valid:** output opens as a valid Word document (zip + document.xml parses).

## Rules (rules/, RT-* numbered, testable — Omer's format)
- **RT-TRUTH-001** tailorer uses only master facts; JD gaps → `[GAP]` note, never a false claim.
- (more to be authored: section-preservation, keyword-injection-from-JD, honest-gap-flagging, no-metric-invention)

## Build sequence (todo)
- [ ] Phase 0 — target-pack scaffold: master-profile skeleton (✅ created), AGENTS.md, rules/, gates, prompts.
- [ ] Phase 1 — harness builds the tailor artifacts (tailor script + tailoring prompt) from a spec, gated.
- [ ] Phase 2 — n8n trigger wrapper (optional).

## Log
### 2026-08-05
- Project initiated. Audited PAI harness (core vs PAI-coupled ~50/50). Chose to extend it (D0).
- Locked D1–D4. Validated schema v2 against real applied-folder resumes.
- Created `master-profile.yaml` v2 skeleton, then POPULATED from Golden Gate + BI Analyst resumes
  (76→75 skill tokens; 4 jobs, 4 projects, 7 metrics). Omer to verify `# CHECK` items.
- Wrote `AGENTS.md` (tailoring conventions) + `rules/tailoring-rules.md` (RT-* numbered rules).
- Built `gates.py` (G1–G4, no-LLM). **Smoke test GREEN:** passes truthful output, catches fabricated
  skills (Kubernetes/Rust) and fabricated numbers (5,000,000/500). Truth-guarantee is now mechanical.
- Built `build_harness.py` — reuses PAI core (`make_llm`, schemas, `write_file`, `run_shell`, LangGraph
  shape); de-PAI'd architect/engineer/reviewer prompts; execution node = Python code-gate (py_compile +
  pytest) replacing sqlfluff/schema-diff. Compiles clean.
- Wrote `spec/tailor-spec.md` (v1: title+summary+keyword_line via `{{token}}` replacement in a Word
  template; T1 tailoring_prompt.py, T2 tailor.py, T3 test_tailor.py; gates enforced).
- READY TO RUN (Omer): create `template.docx` (tokens) + venv + .env key →
  `python build_harness.py spec/tailor-spec.md`. Harness builds the tailor, gated, human-approved.
- Manually tailored (pipeline as engine) real resumes: **Creative Chaos** + **VentureDive** — all gates green.
  template.docx built from We-Are-Revolution docx with {{TITLE}}/{{SUMMARY}}/{{KEYWORD_LINE}}/{{COMPANY}}.

### 2026-08-05 (later) — first harness RUN + upgrades
- **H12:** deterministic content gate (`spec/checks.yaml` + `content_gate` in execution node). Catches
  structurally-incomplete files the LLM reviewer rubber-stamped. Proven: caught missing positioning/metrics/RT-TRUTH-002.
- **H13:** gate failure messages now carry human-authored `guidance` (the HOW-TO-FIX) so the engineer
  self-corrects from the gate alone; MAX_RETRIES 2→3.
- **max_tokens=8000** added to Groq + Gemini in `harness/llm.py` (fixed file-truncation SyntaxErrors).
- **Provider registry extended:** added **anthropic** + **deepseek** (lazy-import) + config models.
- Ran the harness (Groq): **T1 `tailoring_prompt.py` BUILT + approved** (correct, runtime-verified).
  LLM reviewer proved to be NOISE (passed a broken file, false-failed two good ones, missed the real
  brace-bug). Deterministic gates are the real authority.
- **Free-tier walls:** Gemini 20 req/day, then Groq 100k tok/day — both exhausted. The reviewer's big
  prompt was a major token sink.
- **T2/T3 hand-written** (weak free model botched tailor.py; quota dead): `tailor.py` (truth-gated,
  design-preserving, injectable llm_fn) + `test_tailor.py` (3 tests, monkeypatched LLM). **pytest GREEN.**
- Result: **working automated tailor tonight, zero cost.** Only the live LLM call is untested (quota).

### Next (no rush)
- Install `langchain-anthropic` + `langchain-deepseek`; add ANTHROPIC_API_KEY / DEEPSEEK_API_KEY to
  `resume-tailor/.env`. DeepSeek = cheap harness engine; Anthropic for hard tasks.
- Live-run `tailor(...)` on a real JD once a provider has quota → confirms the glue.
- Harness H14: runtime smoke-test gate (import + call). Consider DROPPING the LLM reviewer (noise + token sink).
