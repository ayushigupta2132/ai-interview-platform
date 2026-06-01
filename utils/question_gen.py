# ─────────────────────────────────────────────
#  utils/question_gen.py
#  Generates interview questions via Gemini.
#  Respects difficulty level, question-type
#  distribution, and JD skill-gap priority.
# ─────────────────────────────────────────────

import os
import json
import random
import google.generativeai as genai
from dotenv import load_dotenv
from config import (
    GEMINI_MODEL,
    TIME_LIMITS,
    QUESTION_DISTRIBUTION,
    SKILL_GAP_PRIORITY_WEIGHT,
)

load_dotenv()

_API_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_AVAILABLE = bool(_API_KEY)

if _GEMINI_AVAILABLE:
    genai.configure(api_key=_API_KEY)
else:
    print("[question_gen] WARNING: GEMINI_API_KEY not set — fallback questions will be used.")
print("API KEY FOUND:", bool(_API_KEY))

# ── Question type sequence ────────────────────
# Derived from QUESTION_DISTRIBUTION: 40/20/20/20.
# Fixed 10-slot cycle so any 8-question session
# approximates the exact split deterministically.
_TYPE_SEQUENCE = [
    "technical",  "technical",  "conceptual", "behavioral",
    "scenario",   "technical",  "technical",  "conceptual",
    "behavioral", "scenario",
]
assert len(_TYPE_SEQUENCE) == 10, "Sequence length must stay 10 to match distribution."


# ── Per-type fallback templates ───────────────
# Each entry is a callable: (skill, difficulty) -> question text
_FALLBACK_TEMPLATES: dict[str, callable] = {
    "technical": lambda skill, difficulty: (
        {
            "Easy":   f"What is {skill} and what problem does it solve? Give a basic example of how you would use it.",
            "Medium": f"You need to implement a feature using {skill}. Walk through your approach, the key methods or APIs you would use, and any common pitfalls to watch for.",
            "Hard":   f"Design a production-grade system component that relies heavily on {skill}. Discuss scalability, failure modes, and how you would monitor it in production.",
        }[difficulty]
    ),
    "conceptual": lambda skill, difficulty: (
        {
            "Easy":   f"Explain the core concept behind {skill} in simple terms. Why was it created and what gap does it fill?",
            "Medium": f"Compare {skill} with an alternative approach. What are the trade-offs, and when would you choose one over the other?",
            "Hard":   f"Describe the internal architecture or underlying principles of {skill}. How do its design decisions affect performance and correctness at scale?",
        }[difficulty]
    ),
    "behavioral": lambda skill, difficulty: (
        {
            "Easy":   f"Tell me about a time you first learned or used {skill}. What was the context and what did you take away from that experience?",
            "Medium": f"Describe a situation where working with {skill} led to a challenge. How did you diagnose the problem and what was the outcome?",
            "Hard":   f"Tell me about the most complex project where {skill} was central. Walk me through your decision-making, any trade-offs you navigated, and what you would do differently.",
        }[difficulty]
    ),
    "scenario": lambda skill, difficulty: (
        {
            "Easy":   f"Imagine you are joining a new team and they ask you to set up {skill} from scratch. What are the first three steps you would take?",
            "Medium": f"Suppose your team's {skill}-based service is experiencing intermittent failures in production. How would you investigate, isolate the root cause, and apply a fix?",
            "Hard":   f"Imagine you are leading an architecture review and the team is debating whether to adopt {skill} for a high-traffic, globally distributed system. Make the case for or against, addressing latency, consistency, cost, and team expertise.",
        }[difficulty]
    ),
}


def _pick_question_type(q_index: int) -> str:
    """
    Return the question type for a given 0-based index.
    Cycles over _TYPE_SEQUENCE to maintain the 40/20/20/20 distribution.
    """
    return _TYPE_SEQUENCE[q_index % len(_TYPE_SEQUENCE)]


def _build_fallback(
    q_index: int,
    skill: str,
    difficulty: str,
    q_type: str,
) -> dict:
    """
    Build a type-specific, skill-aware, difficulty-aware fallback question dict.
    Used when Gemini is unavailable or returns unparseable output.
    """
    template_fn = _FALLBACK_TEMPLATES.get(q_type, _FALLBACK_TEMPLATES["technical"])
    question_text = template_fn(skill, difficulty)

    return {
        "id":                q_index,
        "text":              question_text,
        "type":              q_type,
        "difficulty":        difficulty,
        "skill_tag":         skill,
        "time_limit":        TIME_LIMITS[difficulty],
        "expected_keywords": [skill.lower()],
    }


def _select_skill_for_question(
    skill_gaps: list[str],
    matched_skills: list[str],
    jd_skills: list[str],
    previous_skill_tags: list[str],
) -> str:
    """
    Choose which skill to test next.

    Priority order (SKILL_GAP_PRIORITY_WEIGHT enforces gap-first):
      1. Skill gaps not yet tested  ← highest priority
      2. Matched skills not yet tested
      3. Any JD skill (repeats allowed once pool is exhausted)
      4. "General" as last resort

    SKILL_GAP_PRIORITY_WEIGHT (1.5) means gap skills are re-eligible
    for a second test before matched skills are exhausted, ensuring
    gaps receive proportionally more coverage across the session.
    """
    tested_counts: dict[str, int] = {}
    for tag in previous_skill_tags:
        tested_counts[tag] = tested_counts.get(tag, 0) + 1

    # Gap skills: eligible if tested fewer than ceil(SKILL_GAP_PRIORITY_WEIGHT) times
    import math
    gap_max_tests = math.ceil(SKILL_GAP_PRIORITY_WEIGHT)   # = 2 with weight 1.5

    for skill in skill_gaps:
        if tested_counts.get(skill, 0) < gap_max_tests:
            return skill

    # Matched skills: eligible if not yet tested at all
    for skill in matched_skills:
        if tested_counts.get(skill, 0) == 0:
            return skill

    # Fallback: any JD skill (allow repeats)
    if jd_skills:
        return random.choice(jd_skills)

    return "General"


def _build_prompt(
    skill: str,
    difficulty: str,
    q_type: str,
    resume_text: str,
    jd_text: str,
    history: list[dict],
) -> str:
    """Build the Gemini prompt for question generation."""

    history_summary = ""
    if history:
        last_3 = history[-3:]
        lines = [
            f"  Q{i+1} ({h['difficulty']}, {h['type']}): {h['text'][:90]}…"
            for i, h in enumerate(last_3)
        ]
        history_summary = "Recent questions asked (do NOT repeat these):\n" + "\n".join(lines)

    time_hint = TIME_LIMITS[difficulty]

    return f"""You are a senior technical interviewer conducting a mock job interview.

Job Description (first 1000 characters):
{jd_text[:1000]}

Candidate Resume (first 1000 characters):
{resume_text[:1000]}

Your task:
Generate ONE interview question with these EXACT requirements:
- Skill to test: {skill}
- Difficulty: {difficulty}
- Question type: {q_type}
- Time budget for candidate: {time_hint} seconds

Question type definitions:
- technical:   Tests hands-on coding, implementation, or tool-specific knowledge.
- conceptual:  Tests understanding of theory, principles, or the "why" behind a concept.
- behavioral:  Uses STAR format. Must start with "Tell me about a time…" or similar past-tense framing.
- scenario:    Presents a hypothetical situation. Must start with "Imagine you are…" or "Suppose…".

Difficulty calibration:
- Easy:   Foundational knowledge, definitions, simple use-cases. A junior developer should answer confidently.
- Medium: Applied knowledge, trade-offs, moderate depth. Requires practical experience.
- Hard:   System design, deep debugging, architecture decisions, or expert nuance. Only strong candidates answer well.

{history_summary}

Respond with ONLY valid JSON — no markdown, no code fences, no explanation:
{{
  "text": "<the full interview question>",
  "type": "{q_type}",
  "difficulty": "{difficulty}",
  "skill_tag": "{skill}",
  "expected_keywords": ["keyword1", "keyword2", "keyword3"]
}}"""


def generate_question(
    q_index: int,
    difficulty: str,
    skill_gaps: list[str],
    matched_skills: list[str],
    jd_skills: list[str],
    resume_text: str,
    jd_text: str,
    previous_questions: list[dict],
) -> dict:
    """
    Generate a single interview question using Gemini.

    Falls back gracefully (no exception raised) if:
    - GEMINI_API_KEY is missing
    - Gemini returns unparseable JSON
    - Any network or API error occurs

    Args:
        q_index:            0-based index of the current question.
        difficulty:         Current difficulty level ("Easy"/"Medium"/"Hard").
        skill_gaps:         JD skills missing from resume — tested with priority.
        matched_skills:     Skills present in both resume and JD.
        jd_skills:          All skills extracted from JD.
        resume_text:        Raw resume text (first 1000 chars used in prompt).
        jd_text:            Raw JD text (first 1000 chars used in prompt).
        previous_questions: List of already-asked question dicts.

    Returns:
        {
            "id":                int,
            "text":              str,
            "type":              str,
            "difficulty":        str,
            "skill_tag":         str,
            "time_limit":        int,   # from TIME_LIMITS[difficulty]
            "expected_keywords": list[str],
        }
    """
    previous_skill_tags = [q.get("skill_tag", "") for q in previous_questions]

    skill  = _select_skill_for_question(skill_gaps, matched_skills, jd_skills, previous_skill_tags)
    q_type = _pick_question_type(q_index)

    # ── No API key → skip Gemini entirely ────────
    if not _GEMINI_AVAILABLE:
        print(f"[question_gen] No API key — returning fallback for Q{q_index}.")
        return _build_fallback(q_index, skill, difficulty, q_type)

    prompt = _build_prompt(skill, difficulty, q_type, resume_text, jd_text, previous_questions)

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip markdown code fences Gemini occasionally adds despite instructions
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Validate minimum required field
        if not data.get("text", "").strip():
            raise ValueError("Gemini returned empty question text.")

        return {
            "id":                q_index,
            "text":              data["text"].strip(),
            "type":              data.get("type", q_type),
            "difficulty":        data.get("difficulty", difficulty),
            "skill_tag":         data.get("skill_tag", skill),
            "time_limit":        TIME_LIMITS[difficulty],   # always from config, not Gemini
            "expected_keywords": data.get("expected_keywords", []),
        }

    except json.JSONDecodeError as e:
        print(f"[question_gen] JSON parse error on Q{q_index}: {e} — using fallback.")
        return _build_fallback(q_index, skill, difficulty, q_type)

    except ValueError as e:
        print(f"[question_gen] Validation error on Q{q_index}: {e} — using fallback.")
        return _build_fallback(q_index, skill, difficulty, q_type)

    except Exception as e:
        print(f"[question_gen] Gemini error on Q{q_index}: {e} — using fallback.")
        return _build_fallback(q_index, skill, difficulty, q_type)
