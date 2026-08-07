# SPEC — Resume Tailor (v1)

Build the runtime that turns a job post + `master-profile.yaml` into a tailored `.docx` that
preserves the master Word design exactly. The harness (`build_harness.py`) builds the tasks below.

## Prerequisite INPUT (Omer prepares once — not built by the harness)
- `template.docx` — a copy of the master Word resume with **placeholder tokens** in the tailorable spots:
  - `{{TITLE}}` in the header role line
  - `{{SUMMARY}}` in the summary paragraph
  - `{{KEYWORD_LINE}}` in the skills/subtitle keyword line
  All other content (contact, experience, education, design/styles) stays as-is. Robust token
  replacement then preserves the exact design (RT-FORMAT-001).

## Scope (v1)
Tailor **title, summary, and keyword line** only. Bullet selection is v2. No n8n yet.

## Data shapes
- Tailored output (from the LLM): `{"title": str, "summary": str, "keyword_line": [str,...], "gaps": [str,...]}`
- Gates live in `gates.py` (already built): `run_all(output, master, docx_path, present_sections)`.

## Tasks

### T1 — `tailoring_prompt.py`
- `build_prompt(master: dict, job_post: str) -> str` returns the LLM prompt.
- The prompt MUST: (a) include the RT-TRUTH-001/002 rules verbatim in-instruction; (b) instruct the model
  to use ONLY facts from the provided master-profile; (c) require a job requirement the candidate lacks to
  be emitted in `gaps` as "[GAP: <req>]", never claimed; (d) require the literal word "json" and the exact
  output schema `{"title","summary","keyword_line","gaps"}`; (e) embed the master (skills, positioning,
  experience) and the job_post.
- **Acceptance / test (`test_tailor.py::test_prompt`):** prompt contains "RT-TRUTH-001", the job_post text,
  the word "json", and at least one real skill from the master.

### T2 — `tailor.py`
- `tailor(job_post: str, company: str, role: str, master_path="master-profile.yaml",
   template="template.docx") -> str` (returns output .docx path). Pipeline:
  1. Load master (`gates.load_master`). Build prompt (`tailoring_prompt.build_prompt`).
  2. Call the LLM via `harness.llm.make_llm()` with structured/json output → the tailored dict.
  3. Run `gates.run_all(output, master, None, gates.REQUIRED_SECTIONS)`. If it FAILS, re-prompt with the
     gate failures appended, up to 2 retries (RT-TRUTH-001/002 self-correction). If still failing, raise
     with the gate report (never ship a fabrication).
  4. Fill tokens: copy `template.docx`, replace `{{TITLE}}`/`{{SUMMARY}}`/`{{KEYWORD_LINE}}` (from the
     tailored output) and `{{COMPANY}}` (from the `company` arg) in `word/document.xml` at the byte level
     (XML-escape `&`), preserving all else (RT-FORMAT-001).
  5. Save to `applied/<company> - <role>/omer-habib-<company>-<role>.docx` (RT-FILE-001); create folder;
     version-suffix if it exists.
  6. Run `gates.check_placeholders` on the final doc text and `gates.check_docx_valid` on the file; raise on fail.
- Provider is selectable via `LLM_PROVIDER` env (groq|gemini).
- **Acceptance / tests (`test_tailor.py`):** with a MONKEYPATCHED llm returning a fixed truthful dict,
  `tailor(...)` produces a file that (a) opens as valid docx (G4), (b) has no leftover `{{...}}` (G2),
  (c) lands at the RT-FILE-001 path. A fabricated dict (Kubernetes/5,000,000) must raise.

### T3 — `test_tailor.py`
- Pytest covering T1 + T2 acceptance above. Use a fake/monkeypatched LLM (no live API in tests).
- Include a fabrication test: monkeypatched output with an off-master skill → `tailor` raises / gate FAIL.

## Definition of done
`python -m pytest -q` green; a manual `tailor(<sample JD>, "Acme", "Backend Engineer")` produces a
design-preserved `.docx` in `applied/Acme - Backend Engineer/` with tailored title+summary+keywords and
no fabricated content.
