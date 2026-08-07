# Tailoring Rules (RT-*)

Atomic, numbered, testable constraints. Cited by ID in prompts and gates.
Format mirrors PAI's `rules/` (e.g. PAI-ROUTE-001).

## Truth & provenance
- **RT-TRUTH-001** — The tailorer may use ONLY facts present in `master-profile.yaml`. It must never
  introduce a skill, tool, employer, title, or claim absent from it.
  *Gate:* G1 provenance — every skill/tool token in output traces to the master. Untraceable → FAIL.
- **RT-TRUTH-002** — Never invent, inflate, or round metrics. Numbers appear only if present verbatim
  in `master-profile.yaml.metrics` or a bullet.
  *Gate:* G1 — numeric claims cross-checked against master.
- **RT-GAP-001** — If the job post requires something the candidate lacks, it must NOT be claimed.
  Optionally surface it as a `[GAP: <requirement>]` note for Omer's review (the honest-n8n pattern).

## Structure & fidelity
- **RT-SECTION-001** — All required resume sections must be present in the output (contact, summary,
  skills, experience, education). Nothing silently dropped.
  *Gate:* G3 section integrity.
- **RT-FORMAT-001** — Preserve the master `.docx` design exactly. Edit text runs only; never change
  fonts, styles, spacing, or structure; never regenerate the document.
  *Gate:* G4 docx-valid (document opens + parses).
- **RT-PLACEHOLDER-001** — The output must contain no unfilled markers (`{{...}}`, `[COMPANY]`, `TODO`).
  *Gate:* G2 placeholder scan.

## Tailoring behaviour
- **RT-TITLE-001** — The header role/title should mirror the job post's role name when it is a truthful
  framing of the candidate (from `positioning.primary_roles`). Never claim a role never held.
- **RT-KEYWORD-001** — Surface and lead with the candidate's TRUE skills that match the job post's
  language (keyword alignment for ATS + recruiter skim). Only skills present in the master.
- **RT-BULLET-001** — Select and reword the most relevant true bullets from `experience`/`projects`
  for this role. Rewording must not change the underlying fact.
- **RT-TONE-001** — Honest, professional, no fluff. Provenance over fluency: every idea sourced.

## File conventions
- **RT-FILE-001** — Output to `applied/<Company - Role>/omer-habib-<company>-<role>.docx`.
  Create the folder if absent. Do not overwrite an existing tailored file without a version suffix.
