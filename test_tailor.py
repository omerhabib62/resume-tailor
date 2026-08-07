"""
test_tailor.py — no live API; the LLM is faked via llm_fn.
Covers: T1 build_prompt contract, T2 tailor happy-path + RT-TRUTH-001 fabrication rejection.
"""
import os, zipfile, pytest
import tailor as T
from tailoring_prompt import build_prompt
from gates import load_master

MASTER = "master-profile.yaml"


def test_prompt_contains_rules_and_job():
    m = load_master(MASTER)
    jd = "Senior AI Engineer: multi-agent, RAG, Python"
    p = build_prompt(m, jd)
    assert "RT-TRUTH-001" in p          # rules embedded
    assert jd in p                      # job post embedded
    assert "json" in p                  # output format instruction
    assert "Python" in p                # at least one real master skill present


def _truthful_llm(prompt: str) -> dict:
    return {"title": "Senior AI Engineer",
            "summary": "6+ years building production systems; 357 automated tests.",
            "keyword_line": ["Python", "PostgreSQL", "RAG"],
            "gaps": []}


def _fabricated_llm(prompt: str) -> dict:
    return {"title": "Kubernetes Architect",
            "summary": "Handled 5,000,000 users on Rust microservices.",
            "keyword_line": ["Kubernetes", "Rust"],
            "gaps": []}


def test_tailor_produces_valid_docx():
    out = T.tailor("Backend role: Python, PostgreSQL", "TestCo", "Backend Engineer",
                   master_path=MASTER, template="template.docx", llm_fn=_truthful_llm)
    try:
        assert os.path.exists(out)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
        assert "{{" not in xml                         # no leftover tokens (G2)
        assert "Senior AI Engineer" in xml             # tailored title inserted
        assert "TestCo" in xml                         # company inserted
    finally:
        if os.path.exists(out):
            os.remove(out)


def test_tailor_rejects_fabrication():
    with pytest.raises(ValueError):                    # RT-TRUTH-001/002 gate must block it
        T.tailor("role", "TestCo", "Engineer",
                 master_path=MASTER, template="template.docx", llm_fn=_fabricated_llm)
