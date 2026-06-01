# ─────────────────────────────────────────────
#  utils/jd_parser.py
#  Parses a job description (plain text),
#  extracts required skills, and computes the
#  match / gap against the candidate's resume.
# ─────────────────────────────────────────────

import re
from utils.resume_parser import KNOWN_SKILLS   # reuse the same vocabulary


def extract_skills_from_jd(jd_text: str) -> list[str]:
    """
    Match known tech skills against a job description using the same
    rule-based token matching used for resumes.

    Args:
        jd_text: Raw job description string pasted by the user.

    Returns:
        Deduplicated, sorted list of matched skill strings.
    """
    if not jd_text or not jd_text.strip():
        return []

    found: set[str] = set()
    text_lower = jd_text.lower()

    for skill in KNOWN_SKILLS:
        escaped = re.escape(skill.lower())
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(skill)

    return sorted(found)


def compute_matched_skills(
    resume_skills: list[str],
    jd_skills: list[str],
) -> list[str]:
    """
    Return skills present in BOTH the resume and the JD.

    Args:
        resume_skills: Skills extracted from the candidate's resume.
        jd_skills:     Skills extracted from the job description.

    Returns:
        Sorted list of overlapping skills.
    """
    resume_set = {s.lower(): s for s in resume_skills}
    jd_set     = {s.lower() for s in jd_skills}
    matched    = [resume_set[s] for s in jd_set if s in resume_set]
    return sorted(matched)


def compute_skill_gaps(
    resume_skills: list[str],
    jd_skills: list[str],
) -> list[str]:
    """
    Return skills required by the JD but NOT present in the resume.
    These are the candidate's skill gaps.

    Args:
        resume_skills: Skills extracted from the candidate's resume.
        jd_skills:     Skills extracted from the job description.

    Returns:
        Sorted list of missing skills.
    """
    resume_lower = {s.lower() for s in resume_skills}
    gaps = [s for s in jd_skills if s.lower() not in resume_lower]
    return sorted(gaps)


def compute_match_percentage(
    resume_skills: list[str],
    jd_skills: list[str],
) -> float:
    """
    Percentage of JD skills present in the resume.

    Returns:
        Float 0.0–100.0. Returns 0.0 if jd_skills is empty.
    """
    if not jd_skills:
        return 0.0
    matched = compute_matched_skills(resume_skills, jd_skills)
    return round(len(matched) / len(jd_skills) * 100, 1)


def parse_jd(jd_text: str, resume_skills: list[str]) -> dict:
    """
    Full JD parsing pipeline.

    Args:
        jd_text:       Raw job description string.
        resume_skills: Skills already extracted from the candidate's resume.

    Returns:
        {
            "jd_skills":      list[str],   # skills found in JD
            "matched_skills": list[str],   # skills in both JD and resume
            "skill_gaps":     list[str],   # JD skills missing from resume
            "match_pct":      float,       # % of JD skills covered
        }
    """
    jd_skills      = extract_skills_from_jd(jd_text)
    matched_skills = compute_matched_skills(resume_skills, jd_skills)
    skill_gaps     = compute_skill_gaps(resume_skills, jd_skills)
    match_pct      = compute_match_percentage(resume_skills, jd_skills)

    return {
        "jd_skills":      jd_skills,
        "matched_skills": matched_skills,
        "skill_gaps":     skill_gaps,
        "match_pct":      match_pct,
    }
