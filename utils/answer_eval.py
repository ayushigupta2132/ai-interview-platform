# ─────────────────────────────────────────────
#  utils/answer_eval.py
#  Evaluates a candidate's answer using Gemini.
#  Applies timer penalty and computes weighted
#  score using weights from config.py.
# ─────────────────────────────────────────────

import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
from config import (
    GEMINI_MODEL,
    SCORING_WEIGHTS,
    OVERTIME_PENALTY_PER_SECOND,
    MAX_TIMER_PENALTY,
)

load_dotenv()

# ── Logging ───────────────────────────────────
logger = logging.getLogger(__name__)

# ── API key setup (guarded) ───────────────────
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
if _GEMINI_API_KEY:
    genai.configure(api_key=_GEMINI_API_KEY)


# ── Internal helpers ──────────────────────────

def _api_key_valid() -> bool:
    """Return True only if a non-empty API key is present."""
    return bool(_GEMINI_API_KEY)


def _keyword_fallback_score(answer_text: str, expected_keywords: list[str]) -> float:
    """
    Lightweight keyword-based fallback score (0.0–7.0).

    Counts how many expected_keywords appear in the answer (case-insensitive)
    and scales linearly.  Returns 2.0 when no keywords are provided or matched.

    Args:
        answer_text:       Candidate's raw answer.
        expected_keywords: List of keywords from the question dict.

    Returns:
        Float score in [0.0, 7.0].
    """
    if not expected_keywords or not answer_text.strip():
        return 2.0

    lowered = answer_text.lower()
    matched = sum(1 for kw in expected_keywords if kw.lower() in lowered)
    ratio   = matched / len(expected_keywords)

    # Scale: 0 matches → 2.0 (not zero, avoid harsh punishment for partial attempts)
    #        all match → 7.0 (reserve 8–10 for Gemini-verified deep answers)
    score = 2.0 + ratio * 5.0
    return round(score, 2)


def _build_eval_prompt(
    question_text: str,
    answer_text: str,
    difficulty: str,
    skill_tag: str,
    expected_keywords: list[str],
    resume_context: str = "",
    jd_context: str = "",
) -> str:
    """Build the Gemini evaluation prompt, optionally injecting resume and JD context."""

    keywords_hint = ", ".join(expected_keywords) if expected_keywords else "none specified"

    # Build optional context block only when content is available
    context_block = ""
    if resume_context.strip() or jd_context.strip():
        context_block = "\n--- Role Context ---"
        if jd_context.strip():
            context_block += f"\nJob Description Summary:\n{jd_context.strip()}"
        if resume_context.strip():
            context_block += f"\nCandidate Resume Summary:\n{resume_context.strip()}"
        context_block += (
            "\n\nWhen scoring, factor in how well the answer demonstrates "
            "skills relevant to the JD and the candidate's stated background. "
            "Penalise answers that ignore role-specific requirements.\n---"
        )

    return f"""You are an objective technical interview evaluator.
{context_block}
Question asked ({difficulty} difficulty, skill: {skill_tag}):
{question_text}

Candidate's answer:
{answer_text if answer_text.strip() else "[No answer provided — candidate left blank or timed out]"}

Key concepts expected in a good answer: {keywords_hint}

Evaluate the answer on these four dimensions. Score each from 0 to 10:

1. accuracy   — Is the information factually correct? Are there any wrong statements?
2. clarity    — Is the answer well-structured, easy to follow, and clearly communicated?
3. depth      — Does it go beyond surface-level? Does it show genuine understanding?
4. relevance  — Does it directly address what was asked AND align with the role requirements?

Scoring guidelines per difficulty:
- Easy:   A complete basic answer scores 7-8. Exceptional insight scores 9-10.
- Medium: A correct answer with trade-offs scores 6-8. Basic correct scores 5.
- Hard:   Only expert-level depth with nuance scores 8+. Good attempt scores 5-6.

If the answer is blank or clearly nonsensical, score all dimensions 0.

Respond with ONLY valid JSON (no markdown, no code fences):
{{
  "accuracy":  <0-10 float>,
  "clarity":   <0-10 float>,
  "depth":     <0-10 float>,
  "relevance": <0-10 float>,
  "feedback":  "<one concise sentence: what was good and what was missing>"
}}"""


def _compute_time_efficiency(time_taken: float, time_limit: int) -> float:
    """
    Compute time_efficiency score (0–10) based on how the candidate
    used the allotted time.

    - Within limit   → 10.0
    - Over limit     → penalised OVERTIME_PENALTY_PER_SECOND per second,
                       capped at MAX_TIMER_PENALTY points total deduction.
    - Blank / 0 time → treated as overtime equal to full time_limit.

    Args:
        time_taken: Seconds the candidate actually used.
        time_limit: Maximum allowed seconds from config.

    Returns:
        Float score 0.0–10.0.
    """
    if time_taken <= 0:
        # No answer submitted — treat as fully over time
        time_taken = float(time_limit)

    if time_taken <= time_limit:
        return 10.0

    overtime_seconds = time_taken - time_limit
    raw_penalty      = overtime_seconds * OVERTIME_PENALTY_PER_SECOND
    capped_penalty   = min(raw_penalty, MAX_TIMER_PENALTY)

    # MAX_TIMER_PENALTY = 2.0 means up to 2 points off on a 10-pt scale
    score = max(0.0, 10.0 - (capped_penalty * 5))   # 2.0 penalty → −10 pts (floor 0)
    return round(score, 2)


def compute_weighted_score(
    accuracy: float,
    clarity: float,
    depth: float,
    relevance: float,
    time_efficiency: float,
) -> float:
    """
    Apply SCORING_WEIGHTS from config.py to produce a single 0–10 score.

    Args:
        accuracy, clarity, depth, relevance, time_efficiency: Scores 0–10.

    Returns:
        Weighted score rounded to 2 decimal places.
    """
    w = SCORING_WEIGHTS
    score = (
        accuracy        * w["accuracy"]        +
        clarity         * w["clarity"]         +
        depth           * w["depth"]           +
        relevance       * w["relevance"]        +
        time_efficiency * w["time_efficiency"]
    )
    return round(min(10.0, max(0.0, score)), 2)


def evaluate_answer(
    question: dict,
    answer_text: str,
    time_taken: float,
    resume_context: str = "",
    jd_context: str = "",
) -> dict:
    """
    Full evaluation pipeline for one question-answer pair.

    Args:
        question:        The question dict (from generate_question).
        answer_text:     The candidate's raw typed answer.
        time_taken:      Seconds elapsed when the candidate submitted.
        resume_context:  Optional resume summary string for JD-alignment scoring.
        jd_context:      Optional JD summary string for role-relevance scoring.

    Returns:
        {
            "q_index":         int,
            "accuracy":        float,   # 0–10 (Gemini or fallback)
            "clarity":         float,   # 0–10 (Gemini or fallback)
            "depth":           float,   # 0–10 (Gemini or fallback)
            "relevance":       float,   # 0–10 (Gemini or fallback)
            "time_efficiency": float,   # 0–10 (computed from timer)
            "weighted_score":  float,   # 0–10 (final per-question score)
            "difficulty":      str,
            "skill_tag":       str,
            "gemini_feedback": str,     # one-line feedback
        }
    """
    q_index    = question.get("id", 0)
    difficulty = question.get("difficulty", "Easy")
    skill_tag  = question.get("skill_tag", "General")
    time_limit = question.get("time_limit", 120)
    keywords   = question.get("expected_keywords", [])

    # ── Determine initial fallback scores ────────
    is_blank = not answer_text or not answer_text.strip()

    if is_blank:
        fallback_dim = 0.0
        feedback     = "Answer was blank or candidate timed out."
    else:
        # Keyword-based fallback; better than a flat 4.0
        fallback_dim = _keyword_fallback_score(answer_text, keywords)
        feedback     = "Answer analyzed based on technical relevance and expected concepts."

    accuracy  = fallback_dim
    clarity   = fallback_dim
    depth     = fallback_dim
    relevance = fallback_dim

    # ── Guard: skip Gemini if API key is missing ──
    if not _api_key_valid():
        logger.warning(
            "[answer_eval] GEMINI_API_KEY is missing or empty. "
            "Returning fallback evaluation for q_index=%s.", q_index
        )
    elif not is_blank:
        # ── Gemini evaluation ─────────────────────
        prompt = _build_eval_prompt(
            question_text=question.get("text", ""),
            answer_text=answer_text,
            difficulty=difficulty,
            skill_tag=skill_tag,
            expected_keywords=keywords,
            resume_context=resume_context,
            jd_context=jd_context,
        )
        try:
            model    = genai.GenerativeModel(GEMINI_MODEL)
            response = model.generate_content(prompt)
            raw      = response.text.strip()

            # Strip markdown fences if Gemini wraps output anyway
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            data = json.loads(raw)

            accuracy  = float(data.get("accuracy",  fallback_dim))
            clarity   = float(data.get("clarity",   fallback_dim))
            depth     = float(data.get("depth",     fallback_dim))
            relevance = float(data.get("relevance", fallback_dim))
            feedback  = str(data.get("feedback",    feedback))

            # Clamp all Gemini scores to 0–10
            accuracy  = max(0.0, min(10.0, accuracy))
            clarity   = max(0.0, min(10.0, clarity))
            depth     = max(0.0, min(10.0, depth))
            relevance = max(0.0, min(10.0, relevance))

        except json.JSONDecodeError as e:
            logger.warning(
                "[answer_eval] JSON parse error for q_index=%s: %s — using fallback scores.",
                q_index, e
            )
        except Exception as e:
            logger.warning(
                "[answer_eval] Gemini error for q_index=%s: %s — using fallback scores.",
                q_index, e
            )

    # ── Timer score (always computed locally) ────
    time_efficiency = _compute_time_efficiency(time_taken, time_limit)

    # ── Weighted score ────────────────────────────
    weighted_score = compute_weighted_score(
        accuracy, clarity, depth, relevance, time_efficiency
    )

    return {
        "q_index":         q_index,
        "accuracy":        round(accuracy,  2),
        "clarity":         round(clarity,   2),
        "depth":           round(depth,     2),
        "relevance":       round(relevance, 2),
        "time_efficiency": time_efficiency,
        "weighted_score":  weighted_score,
        "difficulty":      difficulty,
        "skill_tag":       skill_tag,
        "gemini_feedback": feedback,
    }
