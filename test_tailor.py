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


def test_rate_limit_detection():
    from tailor import _is_rate_limit
    assert _is_rate_limit("429 RESOURCE_EXHAUSTED: quota exceeded")
    assert _is_rate_limit("Rate limit reached ... tokens per day (TPD): Limit 100000")
    assert not _is_rate_limit("some unrelated json parse error")


def test_quota_error_is_clean(monkeypatch):            # a 429 must surface as a clean LLMError, not a traceback
    class _Boom:
        def invoke(self, prompt):
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota exceeded, tokens per day")
    monkeypatch.setattr("harness.llm.make_llm", lambda *a, **k: _Boom())
    with pytest.raises(T.LLMError) as ei:
        T._default_llm("hi")
    assert "rate/quota" in str(ei.value).lower()


def _string_keyword_llm(prompt: str) -> dict:          # some LLMs return keyword_line as a comma-string
    return {"title": "Backend Engineer",
            "summary": "6+ years building production systems.",
            "keyword_line": "Python, PostgreSQL, RAG",
            "gaps": []}


def test_keyword_line_string_is_normalized():
    out = T.tailor("Backend role: Python", "TestCo2", "Backend Engineer",
                   master_path=MASTER, template="template.docx", llm_fn=_string_keyword_llm)
    try:
        xml = zipfile.ZipFile(out).read("word/document.xml").decode("utf-8", "replace")
        assert "Python · PostgreSQL · RAG" in xml       # words joined
        assert "P · y · t" not in xml                   # NOT rendered character-by-character
    finally:
        if os.path.exists(out):
            os.remove(out)


def test_out_base_redirect(tmp_path):                  # can save outside the project root
    out = T.tailor("Backend: Python", "TmpCo", "Backend Engineer", master_path=MASTER,
                   template="template.docx", llm_fn=_truthful_llm, out_base=str(tmp_path))
    assert str(tmp_path) in out and os.path.exists(out)   # tmp_path auto-cleaned by pytest


def test_provenance_grounds_on_whole_master():
    from gates import check_provenance, load_master
    m = load_master(MASTER)
    base = {"title": "", "summary": "", "bullets": []}
    # legit capability phrasing (grounded in bullets/highlights, not the skills list) must PASS:
    ok = check_provenance({**base, "keyword_line": ["agentic workflows", "multi-agent systems"]}, m)
    assert ok["ok"], ok["output"]
    # genuine fabrication must still FAIL:
    bad = check_provenance({**base, "keyword_line": ["Kubernetes", "Rust"]}, m)
    assert not bad["ok"]
