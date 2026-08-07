# Resume Tailor — a truth-gated resume generator built by a multi-agent build harness

Tailors your résumé to a specific job post **without ever letting the LLM fabricate a skill or a
metric you don't actually have** — enforced in code, not just asked for in a prompt. The design-heavy
part is a **multi-agent build harness** (architect → engineer → reviewer, with deterministic gates)
that *builds* the tailoring tool from a spec.

> Two ideas worth your attention: **(1)** provenance gates that make hallucination mechanically
> impossible, and **(2)** the finding that a deterministic gate beats an LLM "reviewer" every time.

---

## The core idea: provenance over fluency

An LLM asked to "tailor my résumé" will happily invent skills to match the job post. This tool won't,
because a single file — `master-profile.yaml` — is the **only** source of truth, and a **deterministic
provenance gate** checks every claim in the output against it:

```
tailored output → G1 provenance  → every skill/number must trace to master-profile.yaml, else FAIL
                → G2 placeholders → no unfilled {{...}} markers
                → G3 sections     → all required résumé sections present
                → G4 docx-valid   → output opens as a valid Word document
```

If the model tries to add "Kubernetes" or "handled 5,000,000 users" and neither is in your profile,
the gate **rejects it and re-prompts** with the failure. It literally cannot ship a lie.

```python
# gates.py smoke test — truthful output passes, fabricated output fails:
-- BAD (fabricated) --
[G1 provenance] FAIL:
  - RT-TRUTH-001: surfaced skill not in master-profile: 'Kubernetes'
  - RT-TRUTH-002: number '5,000,000' not found in master metrics/bullets
```

Output preserves your **exact Word design** — it does byte-level token replacement
(`{{TITLE}}`/`{{SUMMARY}}`/`{{KEYWORD_LINE}}`/`{{COMPANY}}`) inside `word/document.xml`, never
regenerating the document.

---

## The build harness (the interesting part)

The tailoring tool itself is *built* by a small **LangGraph multi-agent harness** from a spec:

```
spec ─▶ Architect ─▶ [ Engineer ─▶ Execution gate ─▶ Reviewer ─▶ Human gate ] ─▶ done
                        (writes)   (compile + content   (LLM,      (approve /
                                    contract, NO LLM)    optional)   fix notes)
                          ▲───────────── retry with the gate's guidance ──────────┘
```

- **Deterministic content gate** (`spec/checks.yaml`): a human-authored `must_contain` /
  `must_not_contain` contract per file, gre`p`ped after compile. It catches structurally-incomplete
  output the LLM reviewer rubber-stamps — and its failure messages carry **fix guidance**, so the
  engineer self-corrects without a human.
- **Provider-agnostic**: one registry, swap via `LLM_PROVIDER` — `groq` | `gemini` | `anthropic` | `deepseek`.
- **Human-in-the-loop** via LangGraph `interrupt()` + checkpointer.

**A finding from building this:** the LLM "reviewer" node proved *unreliable in both directions* — it
passed a broken file, false-failed two correct ones, and missed the one real runtime bug. The
**deterministic gates are the real authority**; the LLM reviewer is optional garnish. Provenance,
not vibes.

---

## Run it

> 📄 **For the full per-application workflow, see [guide.md](guide.md).**

```bash
pip install -r requirements.txt          # langgraph, langchain-groq/-google-genai, python-docx-free (stdlib zip), pydantic, pyyaml
cp master-profile.example.yaml master-profile.yaml   # then fill with YOUR real facts
# .env:  LLM_PROVIDER=groq   GROQ_API_KEY=...   (or gemini / anthropic / deepseek)

python -m pytest -q                       # tests run with a faked LLM (no API needed)

python -c "from tailor import tailor; print(tailor('<paste a job post>', 'Acme', 'Backend Engineer'))"
```

You also need a `template.docx` — a copy of your résumé with `{{TITLE}}`, `{{SUMMARY}}`,
`{{KEYWORD_LINE}}`, `{{COMPANY}}` typed into those spots. The token-swap preserves everything else.

---

## Layout

| File | Role |
|------|------|
| `master-profile.yaml` | single source of truth (your real facts; gitignored — see the `.example`) |
| `gates.py` | deterministic truth guards (G1–G4) |
| `tailoring_prompt.py` | builds the LLM prompt from the master |
| `tailor.py` | the runtime: prompt → LLM → gates → fill template → save |
| `build_harness.py` | the multi-agent LangGraph harness that builds the above from a spec |
| `spec/`, `rules/`, `AGENTS.md` | the spec, the numbered RT-* rules, and agent conventions |
| `harness/` | vendored generic core (provider registry, schemas, tools) |

## Notes
- Secrets and personal data (`.env`, `master-profile.yaml`, `applied/`, `template.docx`) are gitignored.
- This is a target-pack extending a larger general-purpose build harness; the vendored `harness/` core
  is the reusable, domain-agnostic part.
