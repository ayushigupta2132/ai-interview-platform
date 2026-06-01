# ─────────────────────────────────────────────
#  config.py  —  Central configuration for
#  Hack2Hire AI Mock Interview Platform
# ─────────────────────────────────────────────

# ── Interview Flow ────────────────────────────
TOTAL_QUESTIONS = 8                  # Total questions per interview session

# Legacy constant — kept for backward compatibility with answer_eval.py
# and any other module that still imports it.
# New code should use TIME_LIMITS[difficulty] instead.
TIME_PER_QUESTION_SECONDS = 120      # Seconds allowed per answer (Easy default)

# ── Per-Difficulty Time Limits ─────────────────
# Hard questions are shorter to increase pressure on expert topics.
TIME_LIMITS = {
    "Easy":   120,   # 2 minutes  — foundational answers
    "Medium":  90,   # 90 seconds — applied / trade-off answers
    "Hard":    60,   # 60 seconds — expert / architecture answers
}

# ── Question Type Distribution ────────────────
# Must sum to 1.0. Used by question_gen to enforce the split.
QUESTION_DISTRIBUTION = {
    "technical":  0.40,
    "conceptual": 0.20,
    "behavioral": 0.20,
    "scenario":   0.20,
}

# ── Difficulty Settings ───────────────────────
DIFFICULTY_LEVELS = ["Easy", "Medium", "Hard"]
STARTING_DIFFICULTY = "Easy"

# Score thresholds (out of 10) to adapt difficulty
SCORE_TO_INCREASE_DIFFICULTY = 7    # Score >= this → move to harder level
SCORE_TO_DECREASE_DIFFICULTY = 4    # Score < this  → move to easier level

# ── Early Termination ─────────────────────────
CONSECUTIVE_POOR_ANSWERS_LIMIT = 3  # End interview after N consecutive low scores
POOR_ANSWER_THRESHOLD = 4           # Score < this is considered "poor"

# ── Scoring Weights (must sum to 1.0) ─────────
SCORING_WEIGHTS = {
    "accuracy":        0.30,
    "clarity":         0.20,
    "depth":           0.25,
    "relevance":       0.15,
    "time_efficiency": 0.10,
}

# ── Timer Penalty ─────────────────────────────
# Each second over the limit deducts this many points from raw score
OVERTIME_PENALTY_PER_SECOND = 0.05
MAX_TIMER_PENALTY = 2.0              # Cap total timer penalty at 2 points

# ── Skill Priority ────────────────────────────
# Multiplier applied when selecting skills from the gap list.
# A value > 1.0 means gap skills are preferred more aggressively.
SKILL_GAP_PRIORITY_WEIGHT = 1.5

# ── Resume Parsing ────────────────────────────
MAX_PROJECTS_TO_ANALYZE = 3         # Cap project snippets extracted from resume

# ── Final Readiness Score Bands ───────────────
READINESS_BANDS = {
    "Strong":            (75, 100),
    "Average":           (50, 74),
    "Needs Improvement": (0,  49),
}

# Minimum readiness score to receive a "Hire Recommended" label
HIRING_RECOMMENDATION_THRESHOLD = 65

# ── Gemini Model ──────────────────────────────
# gemini-2.0-flash: best balance of speed, reliability, and quality
# for real-time interview question generation and answer evaluation.
# Upgrade to "gemini-2.5-pro" for maximum reasoning depth if latency
# is acceptable (slower but stronger on hard technical questions).
GEMINI_MODEL = "gemini-2.0-flash"

# ── UI / Display ──────────────────────────────
APP_TITLE = "Hack2Hire"
APP_SUBTITLE = "AI-Powered Mock Interview Platform"
APP_ICON = "🎯"

# Session state stages
STAGE_SETUP      = "setup"       # Upload resume + paste JD
STAGE_READY      = "ready"       # Both inputs confirmed, ready to start
STAGE_INTERVIEW  = "interview"   # Interview in progress
STAGE_TERMINATED = "terminated"  # Ended early due to poor performance
STAGE_RESULTS    = "results"     # Interview complete, showing report
