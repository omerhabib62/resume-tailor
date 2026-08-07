from typing import Dict

def build_prompt(master: Dict, job_post: str) -> str:
    """
    Builds the prompt for the LLM to tailor the resume.

    Args:
        master: The candidate's master profile data.
        job_post: The job post content.

    Returns:
        A prompt string for the LLM.
    """
    positioning = master.get('positioning', {})
    experience = master.get('experience', [])
    metrics = master.get('metrics', {})
    projects = master.get('projects', [])
    skills = master.get('skills', [])
    prompt = f"""
    MASTER PROFILE FACTS:
    Positioning: {positioning}
    Experience: {experience}
    Metrics: {metrics}
    Projects: {projects}
    Skills: {skills}

    RULES:
    RT-TRUTH-001: The tailorer may use ONLY facts present in the master profile.
    RT-TRUTH-002: Never invent or inflate metrics; include a number only if it appears in the master.
    RT-GAP-001: If the job post requires something the candidate lacks, it must NOT be claimed.
    RT-SECTION-001: All required resume sections must be present in the output.
    RT-FORMAT-001: Preserve the master .docx design exactly.
    RT-PLACEHOLDER-001: The output must contain no unfilled markers.
    RT-TITLE-001: The header role/title should mirror the job post's role name when it is a truthful framing of the candidate.
    RT-KEYWORD-001: Surface and lead with the candidate's TRUE skills that match the job post's language.
    RT-BULLET-001: Select and reword the most relevant true bullets from experience/projects for this role.
    RT-TONE-001: Honest, professional, no fluff.

    JOB POST:
    {job_post}

    INSTRUCTIONS FOR LLM:
    Reply ONLY with a json object of this exact shape (include the word 'json'):
      "title": a short role title, 2-5 words, mirroring the job post's role if it is truthful for this candidate.
      "summary": a 3-4 sentence professional summary using ONLY master facts.
      "keyword_line": a list of SHORT skill terms, 1-3 words each, e.g. ["Python", "RAG", "Multi-Agent Systems", "PostgreSQL", "LLM Evaluation"]. NOT sentences, NOT descriptions, NOT punctuation-heavy phrases.
      "gaps": a list of short strings, each a single job requirement the candidate lacks (or []).
    Shape: {{title, summary, keyword_line, gaps}}
    """
    return prompt