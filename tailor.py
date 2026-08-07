"""
tailor.py — automated, truth-gated, design-preserving resume tailoring.

Pipeline: master-profile + job_post -> build_prompt -> LLM (JSON) -> gates.run_all
(truth/provenance self-correction) -> fill template.docx tokens -> save under applied/ -> final gates.

The LLM call is injectable (`llm_fn`) so tests run with NO live API.
"""
from __future__ import annotations
import os, re, io, json, zipfile
from gates import load_master, run_all, check_docx_valid, check_placeholders, REQUIRED_SECTIONS
from tailoring_prompt import build_prompt


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _default_llm(prompt: str) -> dict:
    """Call the configured harness provider (Groq/Gemini/Anthropic/DeepSeek) and parse its JSON reply."""
    from harness.llm import make_llm
    raw = make_llm().invoke(prompt).content
    if isinstance(raw, list):  # some providers return content blocks
        raw = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"LLM did not return JSON:\n{raw[:500]}")
    return json.loads(m.group(0))


def _fill_template(template: str, values: dict[str, str]) -> bytes:
    """Byte-level token replacement inside word/document.xml — preserves the exact design (RT-FORMAT-001)."""
    xml = zipfile.ZipFile(template).read("word/document.xml")
    for token, val in values.items():
        xml = xml.replace(token.encode("utf-8"), _xml_escape(val).encode("utf-8"))
    buf = io.BytesIO()
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            zout.writestr(it, xml if it.filename == "word/document.xml" else zin.read(it.filename))
    return buf.getvalue()


def tailor(job_post: str, company: str, role: str,
           master_path: str = "master-profile.yaml", template: str = "template.docx",
           llm_fn=_default_llm, max_fix: int = 2) -> str:
    master = load_master(master_path)
    prompt = build_prompt(master, job_post)

    # --- LLM tailoring with truth-gate self-correction (RT-TRUTH-001/002) ---
    output, report = None, ""
    for attempt in range(max_fix + 1):
        p = prompt if attempt == 0 else (
            prompt + "\n\nYOUR PREVIOUS OUTPUT FAILED THESE CHECKS. FIX EXACTLY:\n" + report)
        output = llm_fn(p)
        # LLMs sometimes return keyword_line as a comma-string instead of a list — normalize so the
        # provenance gate checks real skill tokens (not characters) and the render joins words, not letters.
        if isinstance(output.get("keyword_line"), str):
            output["keyword_line"] = [s.strip() for s in output["keyword_line"].split(",") if s.strip()]
        res = run_all(output, master, None, REQUIRED_SECTIONS)   # G1 provenance, G2 placeholders, G3 sections
        if res["ok"]:
            break
        report = res["output"]
    else:
        raise ValueError("Tailoring failed the truth gates (RT-TRUTH-001/002):\n" + report)

    # --- fill the Word template (design preserved) ---
    values = {
        "{{TITLE}}": str(output["title"]),
        "{{SUMMARY}}": str(output["summary"]),
        "{{KEYWORD_LINE}}": " · ".join(str(x) for x in output.get("keyword_line", [])),
        "{{COMPANY}}": company,
    }
    doc = _fill_template(template, values)

    # --- save under applied/<Company - Role>/ (RT-FILE-001), version-suffix if it exists ---
    out_dir = os.path.join("applied", f"{company} - {role}")
    os.makedirs(out_dir, exist_ok=True)
    base = f"omer-habib-{company}-{role}".replace(" ", "-")
    out_path = os.path.join(out_dir, base + ".docx")
    n = 2
    while os.path.exists(out_path):
        out_path = os.path.join(out_dir, f"{base}-v{n}.docx"); n += 1
    with open(out_path, "wb") as f:
        f.write(doc)

    # --- final deterministic gates on the produced FILE ---
    g4 = check_docx_valid(out_path)
    if not g4["ok"]:
        raise ValueError(g4["output"])
    final_text = " ".join(re.findall(
        r"<w:t[^>]*>(.*?)</w:t>",
        zipfile.ZipFile(out_path).read("word/document.xml").decode("utf-8", "replace")))
    g2 = check_placeholders(final_text)
    if not g2["ok"]:
        raise ValueError(g2["output"])

    # console feedback for real use: what got generated + honest gaps to handle in a cover note
    print(f"  → title:    {output['title']}")
    print(f"  → keywords: {values['{{KEYWORD_LINE}}']}")
    if output.get("gaps"):
        print("  → [GAPS] (kept OFF the resume — address these in a cover note / interview):")
        for g in output["gaps"]:
            print("      -", g)
    return out_path


if __name__ == "__main__":
    # Manual run (needs a live LLM provider configured in .env)
    print(tailor("Senior AI Engineer — multi-agent systems, RAG, Python, evaluation.",
                 "Acme", "Senior AI Engineer"))
