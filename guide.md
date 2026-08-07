# Usage Guide — tailoring a résumé per application

The step-by-step workflow for using the tailor on a real job application.

## One-time setup
- Copy `master-profile.example.yaml` → `master-profile.yaml` and fill it with **your real facts**
  (this file is the single source of truth; the provenance gate rejects anything not in it).
- Create a `template.docx` — a copy of your résumé with `{{TITLE}}`, `{{SUMMARY}}`, `{{KEYWORD_LINE}}`,
  and `{{COMPANY}}` typed into those spots. Token replacement preserves the rest of the design.
- In `.env`, set your provider + key. **Recommended: `LLM_PROVIDER=gemini`** for real applications —
  it writes cleaner, more truthful summaries than free Groq-llama (which can be flaky). Both have a daily
  free quota.
  ```
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=...
  ```
- **Optional — save resumes elsewhere:** set `OUTPUT_DIR` in `.env` to write tailored files to your own
  folder instead of the project's `applied/`. Example:
  ```
  OUTPUT_DIR=C:\Users\omerh\Documents\KSBL\semesters\2nd semester\other\applied
  ```
  Files land in `OUTPUT_DIR/<Company - Role>/`. Defaults to `applied/` if unset.

## For each job

1. **Paste the job description** into a file called `jd.txt` in the project root (create it, paste the
   full post text, save). `jd.txt` is gitignored — it never gets committed.

2. **Run the CLI:**
   ```bash
   python run.py "Company Name" "Role Title"
   ```
   (Or point at a different file: `python run.py "Company" "Role" other.txt`.)

3. **Read the console output.** It prints:
   - the tailored **title** and **keyword line** — sanity-check they fit the role;
   - the **`[GAPS]`** it flagged — skills the JD wants that you lack. These go in your **cover note /
     DM**, never on the résumé (honest-gap framing);
   - the **output path**: `applied/<Company - Role>/omer-habib-<company>-<role>.docx`.

4. **Open the `.docx`** — confirm the summary reads well and the keywords look right. (Minor known
   quirk: there may be a little blank spacing under the summary from the template — ignore or tidy.)

5. **Export to PDF** (Word → Save As → PDF).

6. **Apply**, and reach the human (recruiter / job poster) directly where you can.

## If a run is blocked
```
❌ Gate blocked the output (this is the truth-guard working)
```
That means the LLM tried to surface a skill/metric **not in your master profile** — the provenance gate
(RT-TRUTH-001/002) stopped it. That's correct behaviour. If it keeps happening, switch
`LLM_PROVIDER=gemini` in `.env` and retry (Gemini stays truthful more reliably than free Groq-llama).

## The whole flow, in one line
`jd.txt` → `python run.py "Co" "Role"` → review console + `.docx` → export PDF → apply.
