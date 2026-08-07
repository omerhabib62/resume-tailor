"""
gates.py — deterministic (NO-LLM) truth guards for the Resume Tailor.

These enforce the RT-* rules mechanically. The tailor runs them on its own output
and self-corrects; the harness reviewer also runs them to verify RT-TRUTH-001.

Structured tailor output shape expected by the provenance gate:
    {
      "title": str,
      "summary": str,
      "keyword_line": [str, ...],     # skills surfaced for this JD
      "bullets": [str, ...],          # selected/reworded experience+project bullets
      "gaps": [str, ...],             # honest [GAP] notes (allowed; not fabrication)
    }
"""
from __future__ import annotations
import re, zipfile
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REQUIRED_SECTIONS = ["contact", "summary", "skills", "experience", "education"]
PLACEHOLDER_PATTERNS = [r"\{\{.*?\}\}", r"\[[A-Z][A-Z _/]{2,}\]", r"\bTODO\b", r"\bTBD\b", r"\bXXX\b"]
_NUM = re.compile(r"\d[\d,\.]*\s?%?\+?")   # matches "357", "10,000+", "78–97%", "40%"


# ---------- master loading + vocabulary ----------
def load_master(path: str = "master-profile.yaml") -> dict:
    if yaml is None:
        raise RuntimeError("pyyaml not installed")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def skill_vocab(master: dict) -> set[str]:
    """Flatten every skill token across all skill categories -> lowercase set."""
    out = set()
    for cat in (master.get("skills") or {}).values():
        for tok in cat or []:
            out.add(_norm(tok))
    return out


def metric_numbers(master: dict) -> set[str]:
    nums = set()
    ye = (master.get("positioning") or {}).get("years_experience")
    if ye:
        nums.add(str(ye))                      # years of experience is a legitimate number
    for m in master.get("metrics") or []:
        nums |= {n.strip() for n in _NUM.findall(m)}
    # numbers embedded in bullets are also legitimate provenance
    for job in master.get("experience") or []:
        for b in job.get("bullets") or []:
            nums |= {n.strip() for n in _NUM.findall(b)}
    for p in master.get("projects") or []:
        for h in p.get("highlights") or []:
            nums |= {n.strip() for n in _NUM.findall(h)}
    return {n for n in nums if n and n not in {".", ","}}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


# ---------- G1: provenance ----------
_STOP = {"and", "or", "the", "a", "an", "of", "with", "for", "in", "to", "on", "using", "via",
         "across", "both", "as", "at", "by", "is", "it", "that", "this", "your", "you"}


def master_text(master: dict) -> str:
    """All truthful text in the master (skills + bullets + highlights + positioning), flattened + lowercased."""
    parts: list[str] = []
    def walk(x):
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(master)
    return " ".join(parts).lower()


def _skill_supported(skill: str, corpus: str) -> bool:
    """Grounded if every significant word of the surfaced skill appears somewhere in the master corpus."""
    words = [w for w in re.findall(r"[a-z0-9+#.]+", skill.lower()) if len(w) > 2 and w not in _STOP]
    return all(w in corpus for w in words) if words else True


def check_provenance(output: dict, master: dict) -> dict:
    """Every surfaced skill must be grounded in the master; every number must trace to a master number."""
    issues = []
    corpus = master_text(master)

    # skills in the keyword line must be grounded in the master (word-level, whole profile)
    for tok in output.get("keyword_line") or []:
        if not _skill_supported(str(tok), corpus):
            issues.append(f"RT-TRUTH-001: surfaced skill not grounded in master-profile: '{tok}'")

    # numbers anywhere in title/summary/bullets must trace to a real master number
    known_nums = metric_numbers(master)
    blob = " ".join([output.get("title", ""), output.get("summary", "")] + (output.get("bullets") or []))
    for n in {x.strip() for x in _NUM.findall(blob)}:
        if _significant(n) and not _num_known(n, known_nums):
            issues.append(f"RT-TRUTH-002: number '{n}' not found in master metrics/bullets")

    return {"ok": not issues, "output": _fmt("G1 provenance", issues)}


def _skill_known(tok: str, vocab: set[str]) -> bool:
    n = _norm(tok)
    # exact, or the surfaced token is a substring of a real skill (or vice-versa)
    return any(n == v or n in v or v in n for v in vocab)


def _significant(n: str) -> bool:
    # ignore bare small integers like years counts "6"; guard real claims (%, commas, "+")
    return ("%" in n) or ("," in n) or ("+" in n) or (len(re.sub(r"[^\d]", "", n)) >= 3)


def _num_known(n: str, known: set[str]) -> bool:
    d = re.sub(r"[^\d]", "", n)
    return any(d and d in re.sub(r"[^\d]", "", k) for k in known)


# ---------- G2: placeholders ----------
def check_placeholders(text: str) -> dict:
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        hits += re.findall(pat, text)
    hits = [h for h in hits if h not in ("[GAP]",)]  # [GAP] notes are allowed
    return {"ok": not hits, "output": _fmt("G2 placeholders", [f"leftover marker: {h}" for h in set(hits)])}


# ---------- G3: section integrity ----------
def check_sections(present: list[str]) -> dict:
    have = {_norm(s) for s in present}
    missing = [s for s in REQUIRED_SECTIONS if s not in have]
    return {"ok": not missing, "output": _fmt("G3 sections", [f"missing section: {s}" for s in missing])}


# ---------- G4: docx validity ----------
def check_docx_valid(path: str) -> dict:
    issues = []
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                issues.append("word/document.xml missing")
            else:
                ET.fromstring(z.read("word/document.xml"))  # raises if malformed
    except Exception as e:
        issues.append(f"docx invalid: {e}")
    return {"ok": not issues, "output": _fmt("G4 docx-valid", issues)}


def _fmt(name: str, issues: list[str]) -> str:
    return f"[{name}] OK" if not issues else f"[{name}] FAIL:\n  - " + "\n  - ".join(issues)


def run_all(output: dict, master: dict, docx_path: str | None, present_sections: list[str]) -> dict:
    text = " ".join([output.get("title", ""), output.get("summary", "")] + (output.get("bullets") or []))
    results = [
        check_provenance(output, master),
        check_placeholders(text),
        check_sections(present_sections),
    ]
    if docx_path:
        results.append(check_docx_valid(docx_path))
    ok = all(r["ok"] for r in results)
    return {"ok": ok, "output": "\n".join(r["output"] for r in results)}


if __name__ == "__main__":
    m = load_master()
    print("skill vocab size:", len(skill_vocab(m)))
    print("known numbers:", sorted(metric_numbers(m))[:12])
    # smoke test: a clean output vs a fabricated one
    good = {"title": "Backend Engineer", "summary": "6 years building NestJS + PostgreSQL systems.",
            "keyword_line": ["NestJS", "PostgreSQL", "Python"], "bullets": ["357 automated tests"], "gaps": []}
    bad = {"title": "Kubernetes Architect", "summary": "Ran 500 microservices.",
           "keyword_line": ["Kubernetes", "Rust"], "bullets": ["handled 5,000,000 users"], "gaps": []}
    print("\n-- GOOD --\n", run_all(good, m, None, REQUIRED_SECTIONS)["output"])
    print("\n-- BAD --\n", run_all(bad, m, None, REQUIRED_SECTIONS)["output"])
