# AGENTS.md — Resume Tailor (target-pack conventions)

Foundational rules every agent in the harness obeys when building or running the Resume Tailor.
This target-pack plugs into the PAI harness (`D:\projects\PAI\harness`).

## 1. Truth is non-negotiable
- The **only** source of candidate facts is `master-profile.yaml`. See `rules/tailoring-rules.md` (RT-*).
- The tailorer SELECTS, REORDERS, REWORDS, EMPHASISES — it never INVENTS.
- Never introduce a skill, tool, employer, title, metric, or claim absent from the master.
- If the job post needs something the candidate lacks → emit a `[GAP]` note; never fake it.

## 2. What is tailorable vs fixed
- **Tailorable** (rewritten per job post): header role/title, subtitle keyword line, summary,
  skills ordering/emphasis, which experience/project bullets are surfaced and how they're worded.
- **Fixed** (never changed): contact block, employer names, roles' true nature, dates, education,
  certifications, and the underlying factual content of any bullet.

## 3. Output = edit a COPY of the master Word .docx
- Preserve the existing design EXACTLY. Apply **targeted text-run edits** inside `document.xml`
  (the proven technique) — never regenerate the document, never alter styles/fonts/layout.
- Escape XML (`&` → `&amp;`). Operate on bytes to avoid encoding corruption.
- Output path: `applied/<Company - Role>/omer-habib-<company>-<role>.docx` (+ optional PDF).

## 4. Uncertainty protocol
- Missing/ambiguous detail → `[NEEDS REVIEW: <what>]` for build tasks, or `[GAP: <jd requirement>]`
  for a tailoring gap. NEVER guess a value to fill a hole.

## 5. Tailoring quality bar (what "good" means)
- Mirror the job post's real language for skills the candidate genuinely has (keyword alignment).
- Lead with the strongest true match to the role.
- Honest about gaps (the n8n "new to me, ramps fast" pattern) — honesty is a feature, not a bug.
- No fluff, no unsourced claims (provenance over fluency).

## 6. Build conventions (for the harness building this tool)
- Python for the tailor + gates. Free LLM tier (Groq `llama-3.3-70b-versatile` / Gemini flash-lite).
- One task at a time; read-before-write (edit, don't regenerate); no omissions; no extras beyond spec.
- Deterministic gates run with NO LLM: provenance (G1), placeholders (G2), sections (G3), docx-valid (G4).
