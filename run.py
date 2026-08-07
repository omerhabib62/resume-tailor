"""
CLI wrapper for the tailor — avoids shell-quoting long job descriptions.

Usage:
    1. Paste the job description into  jd.txt
    2. python run.py "Company Name" "Role Title"        (JD read from jd.txt by default)
       python run.py "Company Name" "Role Title" other.txt   (or a different JD file)

Prints the output .docx path + the honest gaps to address in your cover note.
"""
import os, sys
from dotenv import load_dotenv
from tailor import tailor, LLMError

load_dotenv()   # so OUTPUT_DIR / LLM_PROVIDER from .env are available


def main():
    if len(sys.argv) < 3:
        print('Usage: python run.py "Company" "Role" [jd_file=jd.txt]')
        sys.exit(1)
    company, role = sys.argv[1], sys.argv[2]
    jd_file = sys.argv[3] if len(sys.argv) > 3 else "jd.txt"
    try:
        job_post = open(jd_file, encoding="utf-8").read().strip()
    except FileNotFoundError:
        print(f"'{jd_file}' not found — create it and paste the job description in first.")
        sys.exit(1)
    if not job_post:
        print(f"'{jd_file}' is empty — paste the job description into it first.")
        sys.exit(1)

    out_base = os.getenv("OUTPUT_DIR", "applied")   # set OUTPUT_DIR in .env to save elsewhere (e.g. your real applied folder)
    print(f"Tailoring for {role} @ {company} …  (saving under: {out_base})")
    try:
        path = tailor(job_post, company, role, out_base=out_base)
    except LLMError as e:
        print(f"\n⚠️  {e}")
        sys.exit(3)
    except ValueError as e:
        print("\n❌ Gate blocked the output (this is the truth-guard working):\n", e)
        print("\nTip: if the LLM keeps tripping the provenance gate, switch LLM_PROVIDER=gemini in .env and retry.")
        sys.exit(2)
    print("\n✅ Done:", path)
    print("Next: open it, eyeball the summary, export to PDF, apply.")


if __name__ == "__main__":
    main()
