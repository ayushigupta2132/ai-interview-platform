# ─────────────────────────────────────────────
#  utils/report_gen.py
#  Computes the final Interview Readiness Report
#  from all scored answers, following the exact
#  formulas defined in the state machine design.
# ─────────────────────────────────────────────

import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from config import (
    GEMINI_MODEL,
    TOTAL_QUESTIONS,
    READINESS_BANDS,
    HIRING_RECOMMENDATION_THRESHOLD,
    STAGE_TERMINATED,
)

load_dotenv()

# ── Logging ───────────────────────────────────
logger = logging.getLogger(__name__)

# ── API key setup (guarded) ───────────────────
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if _GEMINI_API_KEY:
    genai.configure(api_key=_GEMINI_API_KEY)


# ── Difficulty multipliers ─────────────────────
_DIFFICULTY_MULTIPLIER = {
    "Easy":   0.8,
    "Medium": 1.0,
    "Hard":   1.2,
}


def _compute_final_score(scores: list[dict], stage: str) -> float:
    """
    Implement the exact 5-step formula from the state machine:

    Step 1 — Apply difficulty multiplier to each weighted_score.
    Step 2 — Adjusted score = min(10, weighted × multiplier).
    Step 3 — Average across all attempted questions.
    Step 4 — Apply completeness factor (penalty if terminated early).
    Step 5 — Scale to 0–100.

    Returns:
        Float 0.0–100.0, rounded to 1 decimal place.
    """
    if not scores:
        return 0.0

    adjusted: list[float] = []
    for s in scores:
        multiplier = _DIFFICULTY_MULTIPLIER.get(s.get("difficulty", "Medium"), 1.0)
        adj = min(10.0, s["weighted_score"] * multiplier)
        adjusted.append(adj)

    raw_average = sum(adjusted) / len(adjusted)

    # Completeness factor
    questions_attempted = len(scores)
    completeness_ratio  = questions_attempted / TOTAL_QUESTIONS

    if stage == STAGE_TERMINATED:
        completeness_factor = 0.7 + (0.3 * completeness_ratio)
    else:
        completeness_factor = 1.0

    final = (raw_average / 10.0) * 100.0 * completeness_factor
    return round(min(100.0, max(0.0, final)), 1)


def _get_band(score: float) -> str:
    """Return the readiness band label for a given score."""
    for band, (low, high) in READINESS_BANDS.items():
        if low <= score <= high:
            return band
    return "Needs Improvement"


def _compute_skill_scores(scores: list[dict]) -> dict[str, float]:
    """
    Average weighted_score per skill_tag across all answered questions.

    Returns:
        { "Python": 7.2, "SQL": 4.5, ... }
    """
    skill_buckets: dict[str, list[float]] = {}
    for s in scores:
        tag = s.get("skill_tag", "General")
        skill_buckets.setdefault(tag, []).append(s["weighted_score"])

    return {
        tag: round(sum(vals) / len(vals), 2)
        for tag, vals in skill_buckets.items()
    }


def _identify_strengths_weaknesses(
    skill_scores: dict[str, float],
) -> tuple[list[str], list[str]]:
    """
    Strengths:  skill_score >= 7.0
    Weaknesses: skill_score <  5.0

    Returns:
        (strengths, weaknesses) — both sorted by score descending / ascending.
    """
    strengths  = sorted(
        [s for s, v in skill_scores.items() if v >= 7.0],
        key=lambda s: -skill_scores[s],
    )
    weaknesses = sorted(
        [s for s, v in skill_scores.items() if v < 5.0],
        key=lambda s: skill_scores[s],
    )
    return strengths, weaknesses


def _fetch_improvement_tips(
    skill_gaps: list[str],
    weaknesses: list[str],
    scores: list[dict],
    jd_text: str,
) -> list[str]:
    """
    Call Gemini once to generate 3–5 actionable, personalised improvement tips.

    Falls back to generic tips if Gemini is unavailable or the API key is missing.
    """
    combined_weak = list(dict.fromkeys(weaknesses + skill_gaps))[:6]  # dedup, cap at 6

    # Build a brief performance summary for the prompt
    perf_lines = []
    for s in scores[-5:]:   # last 5 questions for context
        perf_lines.append(
            f"  - {s['skill_tag']} ({s['difficulty']}): "
            f"score {s['weighted_score']}/10 — {s['gemini_feedback']}"
        )
    perf_summary = "\n".join(perf_lines) if perf_lines else "  No detailed data."

    fallback_tips = [
        f"Focus on strengthening your knowledge of {combined_weak[0]}." if combined_weak else
        "Review core data structures and algorithms on LeetCode (Easy → Medium).",
        "Practice explaining technical concepts out loud using the STAR method for behavioral questions.",
        "Build a small project using the technologies listed in the job description to demonstrate hands-on experience.",
        "Time yourself when answering practice questions — aim to deliver a complete answer within 90 seconds.",
    ]

    # ── Guard: skip Gemini if API key is missing ──
    if not _GEMINI_API_KEY:
        logger.warning(
            "[report_gen] GEMINI_API_KEY is missing or empty. "
            "Returning fallback improvement tips."
        )
        return fallback_tips

    prompt = f"""You are a career coach reviewing a mock interview performance.

Job description snippet:
{jd_text[:400]}

Skills the candidate is weak in or missing: {', '.join(combined_weak) if combined_weak else 'None identified'}

Recent question performance:
{perf_summary}

Generate exactly 4 actionable, specific improvement tips for this candidate.
Each tip must:
- Be 1–2 sentences
- Name a specific resource, technique, or practice (not generic advice)
- Directly address a weakness or skill gap above

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "tips": [
    "<tip 1>",
    "<tip 2>",
    "<tip 3>",
    "<tip 4>"
  ]
}}"""

    try:
        model    = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        raw      = response.text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)
        tips = data.get("tips", [])
        if isinstance(tips, list) and len(tips) >= 2:
            return [str(t) for t in tips[:5]]
        return fallback_tips

    except Exception as e:
        logger.warning(
            "[report_gen] Tips generation error: %s — using fallback tips.", e
        )
        return fallback_tips


def generate_report(
    scores: list[dict],
    skill_gaps: list[str],
    jd_text: str,
    stage: str,
) -> dict:
    """
    Build the complete Interview Readiness Report.

    Args:
        scores:     List of per-question score dicts (from answer_eval).
        skill_gaps: Skills required by JD but missing from resume.
        jd_text:    Raw job description text (for improvement tip context).
        stage:      Current session stage — used to apply completeness penalty.

    Returns:
        {
            "final_score":          float,        # 0–100
            "band":                 str,           # Strong / Average / Needs Improvement
            "hire_recommended":     bool,
            "skill_scores":         dict[str,float],
            "strengths":            list[str],
            "weaknesses":           list[str],
            "improvement_tips":     list[str],
            "questions_attempted":  int,
            "completion_ratio":     float,         # questions_attempted / TOTAL_QUESTIONS
            "termination_reason":   str | None,
            "dimension_averages":   dict[str,float],  # avg per scoring dimension
        }
    """
    if not scores:
        return {
            "final_score":         0.0,
            "band":                "Needs Improvement",
            "hire_recommended":    False,
            "skill_scores":        {},
            "strengths":           [],
            "weaknesses":          [],
            "improvement_tips":    ["Complete at least one question to receive personalised tips."],
            "questions_attempted": 0,
            "completion_ratio":    0.0,
            "termination_reason":  "No questions answered." if stage == STAGE_TERMINATED else None,
            "dimension_averages":  {},
        }

    # ── Core calculations ─────────────────────
    final_score  = _compute_final_score(scores, stage)
    band         = _get_band(final_score)
    hire_ok      = final_score >= HIRING_RECOMMENDATION_THRESHOLD
    skill_scores = _compute_skill_scores(scores)
    strengths, weaknesses = _identify_strengths_weaknesses(skill_scores)

    # ── Completion ratio ──────────────────────
    questions_attempted = len(scores)
    completion_ratio    = round(questions_attempted / TOTAL_QUESTIONS, 3)

    # ── Dimension averages (for radar / bar chart) ──
    dims = ["accuracy", "clarity", "depth", "relevance", "time_efficiency"]
    dimension_averages = {
        d: round(sum(s[d] for s in scores) / len(scores), 2)
        for d in dims
    }

    # ── Improvement tips (Gemini) ─────────────
    improvement_tips = _fetch_improvement_tips(skill_gaps, weaknesses, scores, jd_text)

    # ── Termination reason ─────────────────────
    termination_reason = None
    if stage == STAGE_TERMINATED:
        termination_reason = (
            f"Interview ended early after {len(scores)} question(s) due to "
            "3 consecutive low-scoring answers. "
            "This affects your final score (completeness penalty applied)."
        )

    return {
        "final_score":         final_score,
        "band":                band,
        "hire_recommended":    hire_ok,
        "skill_scores":        skill_scores,
        "strengths":           strengths,
        "weaknesses":          weaknesses,
        "improvement_tips":    improvement_tips,
        "questions_attempted": questions_attempted,
        "completion_ratio":    completion_ratio,
        "termination_reason":  termination_reason,
        "dimension_averages":  dimension_averages,
    }
