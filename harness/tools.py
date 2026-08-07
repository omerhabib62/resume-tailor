import os
import subprocess

# Security: agents may only run vetted commands, never arbitrary shell.
ALLOWED = ("echo", "python", "npm", "node", "ls", "pytest", "sqlfluff")

def check_sql(paths) -> dict:
    """Deterministic SQL parse check — NO LLM. This is the loop's ground truth."""
    sql = [p for p in (paths or []) if p.endswith(".sql")]
    if not sql:
        return {"ok": True, "output": "no .sql files to check"}
    errs = []
    for p in sql:
        res = run_shell(f'sqlfluff parse "{p}" --dialect postgres')
        if not res["ok"]:
            errs.append(f"--- {p} ---\n{res['output'][:2000]}")
    return {"ok": not errs, "output": "\n".join(errs) if errs else "SQL parse OK"}

def _trim_sql_err(output: str) -> str:
    lines = [l for l in output.splitlines()
             if "unparsable" in l.lower() or "Expected" in l or "Found" in l]
    return "\n".join(lines[:20]) or output[:600]

def check_sql(paths) -> dict:
    sql = [p for p in (paths or []) if p.endswith(".sql")]
    if not sql:
        return {"ok": True, "output": "no .sql files to check"}
    errs = []
    for p in sql:
        res = run_shell(f'sqlfluff parse "{p}" --dialect postgres')
        if not res["ok"]:
            errs.append(f"--- {p} ---\n{_trim_sql_err(res['output'])}")
    return {"ok": not errs, "output": "\n".join(errs) if errs else "SQL parse OK"}


def run_shell(cmd: str) -> dict:
    if not cmd.strip().startswith(ALLOWED):
        return {"ok": False, "output": f"BLOCKED: '{cmd}' not in allow-list", "code": -1}
    proc = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=120
    )
    return {
        "ok": proc.returncode == 0,
        "output": (proc.stdout + proc.stderr).strip(),
        "code": proc.returncode,
    }

def write_file(path: str, content: str) -> dict:
    full = os.path.abspath(path)
    if not full.startswith(os.path.abspath(".")):      # confine writes to the repo
        return {"ok": False, "msg": f"BLOCKED: {path} outside repo"}
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "msg": f"wrote {path}"}
