# ─────────────────────────────────────────────
#  app.py  —  Hack2Hire AI Mock Interview Platform
#  Full Integration: Setup → Interview → Results
# ─────────────────────────────────────────────

import html as html_lib
import time
import streamlit as st

# ── Optional autorefresh (graceful degradation) ──
try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH_AVAILABLE = True
except ImportError:
    _AUTOREFRESH_AVAILABLE = False

from config import (
    APP_TITLE, APP_SUBTITLE, APP_ICON,
    STAGE_SETUP, STAGE_READY, STAGE_INTERVIEW,
    STAGE_TERMINATED, STAGE_RESULTS,
    TOTAL_QUESTIONS, TIME_LIMITS, STARTING_DIFFICULTY,
    DIFFICULTY_LEVELS,
    SCORE_TO_INCREASE_DIFFICULTY, SCORE_TO_DECREASE_DIFFICULTY,
    CONSECUTIVE_POOR_ANSWERS_LIMIT, POOR_ANSWER_THRESHOLD,
)
from utils.resume_parser import parse_resume
from utils.jd_parser      import parse_jd
from utils.question_gen   import generate_question
from utils.answer_eval    import evaluate_answer
from utils.report_gen     import generate_report

# ── Page Config ───────────────────────────────
st.set_page_config(
    page_title=f"{APP_TITLE} — {APP_SUBTITLE}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Background */
.stApp {
    background: #0d0f14;
    color: #e8e9ed;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #13161d !important;
    border-right: 1px solid #1f2330;
}
[data-testid="stSidebar"] * {
    color: #b0b4c1 !important;
}

/* Main headings */
h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.02em;
}

/* Brand title in sidebar */
.brand-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem;
    font-weight: 800;
    color: #f0c04a !important;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin-bottom: 0.2rem;
}
.brand-sub {
    font-size: 0.72rem;
    color: #5a6080 !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 500;
}

/* Step badges in sidebar */
.step-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    font-size: 0.82rem;
    font-weight: 500;
    margin-bottom: 0.4rem;
    width: 100%;
    border: 1px solid transparent;
}
.step-done    { background: #0e2a1a; border-color: #1a5c35; color: #4ade80 !important; }
.step-active  { background: #1e1a08; border-color: #7a5c10; color: #f0c04a !important; }
.step-pending { background: #131620; border-color: #1f2330; color: #4a5070 !important; }

/* Cards */
.upload-card {
    background: #13161d;
    border: 1px solid #1f2330;
    border-radius: 14px;
    padding: 1.75rem 2rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s;
}
.upload-card:hover { border-color: #2e3450; }
.card-label {
    font-family: 'Syne', sans-serif;
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #f0c04a;
    margin-bottom: 0.4rem;
}
.card-title {
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: #e8e9ed;
    margin-bottom: 0.5rem;
}
.card-desc {
    font-size: 0.83rem;
    color: #5a6080;
    margin-bottom: 1.2rem;
    line-height: 1.5;
}

/* Text preview box */
.text-preview {
    background: #0a0c10;
    border: 1px solid #1f2330;
    border-left: 3px solid #f0c04a;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    font-size: 0.8rem;
    line-height: 1.7;
    color: #9aa0b8;
    max-height: 240px;
    overflow-y: auto;
    white-space: pre-wrap;
    font-family: 'DM Sans', monospace;
}

/* Success / warning pills */
.status-pill {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.pill-ok  { background: #0e2a1a; color: #4ade80; border: 1px solid #1a5c35; }
.pill-no  { background: #1e0f0f; color: #f87171; border: 1px solid #5c1a1a; }

/* CTA Button override */
.stButton > button {
    background: #f0c04a !important;
    color: #0d0f14 !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 2.5rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }
.stButton > button:disabled {
    background: #1f2330 !important;
    color: #3a4060 !important;
}

/* Interview question card */
.q-card {
    background: #13161d;
    border: 1px solid #2e3450;
    border-left: 4px solid #f0c04a;
    border-radius: 14px;
    padding: 1.75rem 2rem;
    margin-bottom: 1.5rem;
}
.q-meta {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #5a6080;
    margin-bottom: 0.75rem;
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}
.q-meta .tag {
    padding: 0.2rem 0.6rem;
    border-radius: 5px;
    background: #1f2330;
    color: #9aa0b8;
}
.q-meta .tag-diff-easy   { background: #0e2a1a; color: #4ade80; }
.q-meta .tag-diff-medium { background: #1e1a08; color: #f0c04a; }
.q-meta .tag-diff-hard   { background: #1e0f0f; color: #f87171; }
.q-text {
    font-family: 'Syne', sans-serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: #e8e9ed;
    line-height: 1.5;
}

/* Timer bar */
.timer-wrap {
    background: #13161d;
    border: 1px solid #1f2330;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
}
.timer-label {
    font-size: 0.75rem;
    color: #5a6080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}
.timer-value {
    font-family: 'Syne', sans-serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: #f0c04a;
}
.timer-value.warning { color: #f87171; }

/* Score feedback card */
.feedback-card {
    background: #13161d;
    border: 1px solid #1f2330;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-top: 1rem;
}
.feedback-score {
    font-family: 'Syne', sans-serif;
    font-size: 2rem;
    font-weight: 800;
    color: #f0c04a;
}
.feedback-label {
    font-size: 0.8rem;
    color: #5a6080;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
.feedback-text {
    font-size: 0.85rem;
    color: #9aa0b8;
    line-height: 1.6;
    margin-top: 0.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid #1f2330;
}

/* Dimension row */
.dim-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.35rem 0;
    border-bottom: 1px solid #1a1d28;
    font-size: 0.82rem;
}
.dim-name  { color: #9aa0b8; }
.dim-score { font-weight: 600; color: #f0c04a; }

/* Results */
.report-hero {
    background: linear-gradient(135deg, #13161d 0%, #1a1d2e 100%);
    border: 1px solid #2e3450;
    border-radius: 16px;
    padding: 2.5rem;
    text-align: center;
    margin-bottom: 2rem;
}
.report-score-big {
    font-family: 'Syne', sans-serif;
    font-size: 4.5rem;
    font-weight: 800;
    color: #f0c04a;
    line-height: 1;
}
.report-band {
    font-size: 1rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    margin-top: 0.5rem;
}
.band-strong   { color: #4ade80; }
.band-average  { color: #f0c04a; }
.band-weak     { color: #f87171; }

.hire-badge {
    display: inline-block;
    padding: 0.4rem 1.2rem;
    border-radius: 99px;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-top: 1rem;
}
.hire-yes { background: #0e2a1a; color: #4ade80; border: 1px solid #1a5c35; }
.hire-no  { background: #1e0f0f; color: #f87171; border: 1px solid #5c1a1a; }

.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: #f0c04a;
    margin-bottom: 0.75rem;
}

.skill-pill {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    margin: 0.2rem;
}
.skill-strong { background: #0e2a1a; color: #4ade80; border: 1px solid #1a5c35; }
.skill-weak   { background: #1e0f0f; color: #f87171; border: 1px solid #5c1a1a; }
.skill-gap    { background: #1e1a08; color: #f0c04a; border: 1px solid #7a5c10; }

.tip-card {
    background: #13161d;
    border: 1px solid #1f2330;
    border-left: 3px solid #f0c04a;
    border-radius: 10px;
    padding: 0.9rem 1.1rem;
    margin-bottom: 0.6rem;
    font-size: 0.83rem;
    color: #9aa0b8;
    line-height: 1.6;
}

.terminated-banner {
    background: #1e0f0f;
    border: 1px solid #5c1a1a;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.5rem;
    color: #f87171;
    font-size: 0.88rem;
    line-height: 1.6;
}

/* Progress bar custom */
.progress-wrap {
    background: #1f2330;
    border-radius: 99px;
    height: 6px;
    margin: 0.5rem 0 1.5rem;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 99px;
    background: linear-gradient(90deg, #f0c04a, #e8a020);
    transition: width 0.4s ease;
}

/* Divider */
hr { border-color: #1f2330 !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: #0a0c10 !important;
    border: 1px dashed #2e3450 !important;
    border-radius: 10px !important;
}
[data-testid="stFileUploader"] * { color: #5a6080 !important; }

/* Text area */
textarea {
    background: #0a0c10 !important;
    border: 1px solid #1f2330 !important;
    border-radius: 10px !important;
    color: #9aa0b8 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important;
}
textarea:focus { border-color: #f0c04a !important; box-shadow: none !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d0f14; }
::-webkit-scrollbar-thumb { background: #2e3450; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  SESSION STATE INITIALISATION
# ══════════════════════════════════════════════

def init_session_state():
    defaults = {
        # Stage
        "stage":               STAGE_SETUP,
        # Raw inputs
        "resume_text":         None,
        "jd_text":             None,
        # Parsed data
        "resume_skills":       [],
        "resume_projects":     [],
        "jd_skills":           [],
        "matched_skills":      [],
        "skill_gaps":          [],
        "match_pct":           0.0,
        # Interview state
        "current_q_index":     0,
        "difficulty":          STARTING_DIFFICULTY,
        "poor_streak":         0,
        "questions":           [],
        "answers":             [],
        "scores":              [],
        # Timing
        "interview_start_time": None,
        "q_start_time":         None,
        # Results
        "report":               None,
        # UI helpers
        "_last_resume":         None,
        "_show_feedback":       False,
        "_last_eval":           None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ══════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════

def both_inputs_ready() -> bool:
    return (
        st.session_state["resume_text"] is not None
        and len(st.session_state["resume_text"].strip()) > 50
        and st.session_state["jd_text"] is not None
        and len(st.session_state["jd_text"].strip()) > 50
    )


def elapsed_seconds() -> float:
    """Seconds elapsed since the current question started."""
    if st.session_state["q_start_time"] is None:
        return 0.0
    return time.time() - st.session_state["q_start_time"]


def current_time_limit() -> int:
    return TIME_LIMITS.get(st.session_state["difficulty"], 120)


def adjust_difficulty(score: float):
    """Mutate session difficulty up/down based on last score."""
    idx = DIFFICULTY_LEVELS.index(st.session_state["difficulty"])
    if score >= SCORE_TO_INCREASE_DIFFICULTY:
        st.session_state["difficulty"] = DIFFICULTY_LEVELS[min(idx + 1, len(DIFFICULTY_LEVELS) - 1)]
    elif score < SCORE_TO_DECREASE_DIFFICULTY:
        st.session_state["difficulty"] = DIFFICULTY_LEVELS[max(idx - 1, 0)]


def check_early_termination() -> bool:
    """Return True if interview should end early."""
    return st.session_state["poor_streak"] >= CONSECUTIVE_POOR_ANSWERS_LIMIT


# ══════════════════════════════════════════════
#  SIDEBAR  (shared across all stages)
# ══════════════════════════════════════════════

def render_sidebar():
    stage = st.session_state["stage"]
    with st.sidebar:
        st.markdown('<div class="brand-title">Hack2Hire 🎯</div>', unsafe_allow_html=True)
        st.markdown('<div class="brand-sub">AI Mock Interview Platform</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("**Interview Progress**")
        st.markdown("<br>", unsafe_allow_html=True)

        resume_ready = st.session_state["resume_text"] is not None
        jd_ready     = st.session_state["jd_text"] is not None
        in_interview = stage in (STAGE_INTERVIEW, STAGE_TERMINATED)
        in_results   = stage == STAGE_RESULTS

        def badge(cls, ico, label):
            st.markdown(
                f'<div class="step-badge {cls}">{ico}&nbsp; {label}</div>',
                unsafe_allow_html=True,
            )

        badge(
            "step-done" if resume_ready else "step-active",
            "✅" if resume_ready else "📄",
            "Step 1 — Upload Resume",
        )
        badge(
            "step-done" if jd_ready else ("step-active" if resume_ready else "step-pending"),
            "✅" if jd_ready else "📋",
            "Step 2 — Paste Job Description",
        )
        badge(
            "step-done" if in_results else ("step-active" if in_interview else "step-pending"),
            "✅" if in_results else ("🎙" if in_interview else "🚀"),
            "Step 3 — Interview",
        )
        badge(
            "step-active" if in_results else "step-pending",
            "📊",
            "Step 4 — View Report",
        )

        # Live interview stats
        if in_interview:
            st.markdown("<hr>", unsafe_allow_html=True)
            q_idx = st.session_state["current_q_index"]
            st.markdown(f"**Question** {q_idx + 1} / {TOTAL_QUESTIONS}")
            diff       = st.session_state["difficulty"]
            diff_color = {"Easy": "#4ade80", "Medium": "#f0c04a", "Hard": "#f87171"}.get(diff, "#f0c04a")
            st.markdown(
                f'<span style="font-size:0.8rem;color:{diff_color};font-weight:600;">'
                f'Difficulty: {diff}</span>',
                unsafe_allow_html=True,
            )
            if st.session_state["scores"]:
                avg = sum(s["weighted_score"] for s in st.session_state["scores"]) / len(st.session_state["scores"])
                st.markdown(
                    f'<span style="font-size:0.8rem;color:#9aa0b8;">Avg score: {avg:.1f}/10</span>',
                    unsafe_allow_html=True,
                )

        # Skill match info
        if st.session_state["match_pct"]:
            st.markdown("<hr>", unsafe_allow_html=True)
            pct   = st.session_state["match_pct"]
            color = "#4ade80" if pct >= 60 else ("#f0c04a" if pct >= 35 else "#f87171")
            st.markdown(
                f'<span style="font-size:0.8rem;color:{color};font-weight:600;">'
                f'Resume match: {pct:.0f}%</span>',
                unsafe_allow_html=True,
            )
            gaps = st.session_state.get("skill_gaps", [])
            if gaps:
                st.markdown(
                    f'<span style="font-size:0.75rem;color:#5a6080;">Gaps: {", ".join(gaps[:4])}'
                    f'{"…" if len(gaps) > 4 else ""}</span>',
                    unsafe_allow_html=True,
                )

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            '<span style="font-size:0.75rem;color:#3a4060;">Powered by Gemini · Built for Hack2Hire</span>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════
#  STAGE: SETUP
# ══════════════════════════════════════════════

def render_setup():
    st.markdown(
        '<h1 style="font-family:Syne,sans-serif;font-size:2.4rem;'
        'font-weight:800;color:#e8e9ed;margin-bottom:0.1rem;">'
        'AI Mock <span style="color:#f0c04a;">Interview</span></h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#5a6080;font-size:0.9rem;margin-top:0;margin-bottom:2rem;">'
        'Upload your resume and paste a job description to get a personalised interview session.</p>',
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1, 1], gap="large")

    # ── Left: Resume ──────────────────────────
    with col_left:
        st.markdown(
            '<div class="upload-card">'
            '<div class="card-label">Step 01</div>'
            '<div class="card-title">Upload Your Resume</div>'
            '<div class="card-desc">PDF format only. Skills and experience will be extracted '
            'automatically to personalise your interview questions.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        resume_file = st.file_uploader(
            label="Drop your resume PDF here",
            type=["pdf"],
            key="resume_uploader",
            label_visibility="collapsed",
        )

        if resume_file is not None:
            if (st.session_state["resume_text"] is None
                    or st.session_state.get("_last_resume") != resume_file.name):
                with st.spinner("Extracting resume…"):
                    try:
                        parsed = parse_resume(resume_file)
                        if len(parsed["text"].strip()) < 50:
                            st.error("⚠️ Could not extract enough text. Ensure the PDF is not scanned/image-only.")
                        else:
                            st.session_state["resume_text"]    = parsed["text"]
                            st.session_state["resume_skills"]  = parsed.get("skills", [])
                            st.session_state["resume_projects"] = parsed.get("projects", [])
                            st.session_state["_last_resume"]   = resume_file.name
                    except Exception as e:
                        st.error(f"Failed to read PDF: {e}")

        if st.session_state["resume_text"]:
            wc     = len(st.session_state["resume_text"].split())
            skills = st.session_state["resume_skills"]
            st.markdown(
                f'<span class="status-pill pill-ok">✓ Resume loaded — {wc} words'
                f'{f", {len(skills)} skills" if skills else ""}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("📄 Preview extracted resume text", expanded=False):
                st.markdown(
                    f'<div class="text-preview">{st.session_state["resume_text"][:2000]}'
                    f'{"…" if len(st.session_state["resume_text"]) > 2000 else ""}</div>',
                    unsafe_allow_html=True,
                )
            if skills:
                with st.expander("🧠 Detected skills", expanded=False):
                    st.markdown(
                        " ".join(
                            f'<span class="skill-pill skill-strong">{s}</span>'
                            for s in skills
                        ),
                        unsafe_allow_html=True,
                    )
            if st.button("🗑 Remove Resume", key="clear_resume"):
                # FIX 2: _last_resume must reset to None, not []
                for k in ("resume_text", "_last_resume", "resume_skills",
                          "resume_projects", "jd_skills", "matched_skills", "skill_gaps"):
                    st.session_state[k] = None if k in ("resume_text", "_last_resume") else []
                st.session_state["match_pct"] = 0.0
                st.rerun()
        else:
            st.markdown(
                '<span class="status-pill pill-no">✗ No resume uploaded yet</span>',
                unsafe_allow_html=True,
            )

    # ── Right: JD ─────────────────────────────
    with col_right:
        st.markdown(
            '<div class="upload-card">'
            '<div class="card-label">Step 02</div>'
            '<div class="card-title">Paste Job Description</div>'
            '<div class="card-desc">Copy the full job description from any job portal. '
            'Required skills will be matched against your resume.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        jd_input = st.text_area(
            label="Paste JD here",
            placeholder="Paste the full job description here…\n\nExample:\nWe are looking for a Python Developer with experience in Django, REST APIs, SQL, and AWS…",
            height=260,
            key="jd_textarea",
            label_visibility="collapsed",
        )

        save_jd_btn = st.button("💾 Save Job Description", key="save_jd")
        if save_jd_btn:
            if jd_input and len(jd_input.strip()) > 50:
                with st.spinner("Analysing job description…"):
                    try:
                        parsed_jd = parse_jd(
                            jd_input.strip(),
                            st.session_state.get("resume_skills", []),
                        )
                        st.session_state["jd_text"]        = jd_input.strip()
                        st.session_state["jd_skills"]      = parsed_jd.get("jd_skills", [])
                        st.session_state["matched_skills"] = parsed_jd.get("matched_skills", [])
                        st.session_state["skill_gaps"]     = parsed_jd.get("skill_gaps", [])
                        st.session_state["match_pct"]      = parsed_jd.get("match_pct", 0.0)
                    except Exception as e:
                        st.session_state["jd_text"] = jd_input.strip()
                        st.warning(f"JD parsed with limited analysis: {e}")
            else:
                st.warning("Please paste a meaningful job description (at least 50 characters).")

        if st.session_state["jd_text"]:
            wc   = len(st.session_state["jd_text"].split())
            pct  = st.session_state.get("match_pct", 0.0)
            gaps = st.session_state.get("skill_gaps", [])
            st.markdown(
                f'<span class="status-pill pill-ok">✓ JD saved — {wc} words'
                f'{f" · {pct:.0f}% resume match" if pct else ""}</span>',
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("📋 Preview saved JD", expanded=False):
                st.markdown(
                    f'<div class="text-preview">{st.session_state["jd_text"][:2000]}'
                    f'{"…" if len(st.session_state["jd_text"]) > 2000 else ""}</div>',
                    unsafe_allow_html=True,
                )
            if gaps:
                with st.expander("⚠️ Skill gaps detected", expanded=False):
                    st.markdown(
                        " ".join(
                            f'<span class="skill-pill skill-gap">{g}</span>'
                            for g in gaps
                        ),
                        unsafe_allow_html=True,
                    )
            if st.button("🗑 Clear JD", key="clear_jd"):
                for k in ("jd_text", "jd_skills", "matched_skills", "skill_gaps"):
                    st.session_state[k] = None if k == "jd_text" else []
                st.session_state["match_pct"] = 0.0
                st.rerun()
        else:
            st.markdown(
                '<span class="status-pill pill-no">✗ No job description saved yet</span>',
                unsafe_allow_html=True,
            )

    # ── CTA ───────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    cta_col, info_col = st.columns([1, 2], gap="large")

    with cta_col:
        ready     = both_inputs_ready()
        start_btn = st.button(
            "🚀 Begin Interview",
            key="start_interview",
            disabled=not ready,
            use_container_width=True,
        )
        if start_btn and ready:
            st.session_state["stage"]                = STAGE_INTERVIEW
            st.session_state["current_q_index"]      = 0
            st.session_state["difficulty"]           = STARTING_DIFFICULTY
            st.session_state["poor_streak"]          = 0
            st.session_state["questions"]            = []
            st.session_state["answers"]              = []
            st.session_state["scores"]               = []
            st.session_state["report"]               = None
            st.session_state["interview_start_time"] = time.time()
            st.session_state["q_start_time"]         = None
            st.session_state["_show_feedback"]       = False
            st.session_state["_last_eval"]           = None
            st.rerun()

    with info_col:
        if both_inputs_ready():
            pct  = st.session_state.get("match_pct", 0.0)
            gaps = st.session_state.get("skill_gaps", [])
            body = (
                f'Resume match with JD: <strong style="color:#4ade80;">{pct:.0f}%</strong>. '
                + (
                    f'Skill gaps to practise: <strong style="color:#f0c04a;">'
                    f'{", ".join(gaps[:3])}{"…" if len(gaps) > 3 else ""}</strong>. '
                    if gaps else ""
                )
                + 'Click "Begin Interview" to start your AI-powered session.'
            )
            st.markdown(
                f'<div style="background:#0e2a1a;border:1px solid #1a5c35;border-radius:10px;'
                f'padding:1rem 1.25rem;">'
                f'<span style="color:#4ade80;font-weight:600;font-size:0.85rem;">✓ Ready to interview</span><br>'
                f'<span style="color:#5a8060;font-size:0.78rem;line-height:1.6;">{body}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            missing = []
            if not st.session_state["resume_text"]: missing.append("Resume PDF")
            if not st.session_state["jd_text"]:     missing.append("Job Description")
            missing_str = " &amp; ".join(missing)
            st.markdown(
                f'<div style="background:#1e1a08;border:1px solid #7a5c10;border-radius:10px;'
                f'padding:1rem 1.25rem;">'
                f'<span style="color:#f0c04a;font-weight:600;font-size:0.85rem;">⏳ Waiting for inputs</span><br>'
                f'<span style="color:#7a6030;font-size:0.78rem;line-height:1.6;">'
                f'Still needed: <strong style="color:#a07828;">{missing_str}</strong>. '
                f'Complete both steps above to unlock the interview.</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with st.expander("🛠 Session State (debug view)", expanded=False):
        st.json({
            "stage":         st.session_state["stage"],
            "resume_loaded": st.session_state["resume_text"] is not None,
            "resume_skills": st.session_state["resume_skills"],
            "jd_loaded":     st.session_state["jd_text"] is not None,
            "jd_skills":     st.session_state["jd_skills"],
            "skill_gaps":    st.session_state["skill_gaps"],
            "match_pct":     st.session_state["match_pct"],
        })


# ══════════════════════════════════════════════
#  STAGE: INTERVIEW
# ══════════════════════════════════════════════

def render_interview():
    # FIX 3: autorefresh every 3 s so the timer ticks and auto-timeout fires.
    # Falls back gracefully if streamlit-autorefresh is not installed.
    if _AUTOREFRESH_AVAILABLE:
        st_autorefresh(interval=1000, key="q_timer_refresh")
    else:
        st.info(
            "⚠️ Install `streamlit-autorefresh` for live timer countdown and auto-timeout. "
            "Run: `pip install streamlit-autorefresh`",
            icon="⏱",
        )

    q_idx      = st.session_state["current_q_index"]
    difficulty = st.session_state["difficulty"]

    # ── Header ────────────────────────────────
    st.markdown(
        '<h1 style="font-family:Syne,sans-serif;font-size:2rem;'
        'font-weight:800;color:#e8e9ed;margin-bottom:0.25rem;">'
        '🎙 <span style="color:#f0c04a;">Interview</span> in Progress</h1>',
        unsafe_allow_html=True,
    )

    # Progress bar
    progress_pct = int((q_idx / TOTAL_QUESTIONS) * 100)
    st.markdown(
        f'<div class="progress-wrap">'
        f'<div class="progress-fill" style="width:{progress_pct}%;"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    diff_color = {"Easy": "#4ade80", "Medium": "#f0c04a", "Hard": "#f87171"}.get(difficulty, "#f0c04a")
    st.markdown(
        f'<p style="color:#5a6080;font-size:0.82rem;margin-bottom:1.5rem;">'
        f'Question {q_idx + 1} of {TOTAL_QUESTIONS} &nbsp;·&nbsp; '
        f'Difficulty: <strong style="color:{diff_color};">{difficulty}</strong></p>',
        unsafe_allow_html=True,
    )

    # ── Generate question if not yet created ──
    if q_idx >= len(st.session_state["questions"]):
        with st.spinner("Generating question…"):
            try:
                # FIX 1: all eight parameters matching generate_question() exactly
                q = generate_question(
                    q_index            = q_idx,
                    difficulty         = difficulty,
                    skill_gaps         = st.session_state["skill_gaps"],
                    matched_skills     = st.session_state["matched_skills"],
                    jd_skills          = st.session_state["jd_skills"],
                    resume_text        = st.session_state.get("resume_text", ""),
                    jd_text            = st.session_state.get("jd_text", ""),
                    previous_questions = st.session_state["questions"],
                )
            except Exception as e:
                st.error(f"Question generation failed: {e}")
                st.stop()

        st.session_state["questions"].append(q)
        st.session_state["q_start_time"]   = time.time()
        st.session_state["_show_feedback"] = False
        st.session_state["_last_eval"]     = None
        st.rerun()

    question   = st.session_state["questions"][q_idx]
    time_limit = question.get("time_limit", current_time_limit())

    # ── Feedback screen (after answer submission) ──
    if st.session_state.get("_show_feedback") and st.session_state.get("_last_eval"):
        _render_feedback_and_advance(question, time_limit)
        return

    # ── Timer ─────────────────────────────────
    if st.session_state["q_start_time"] is None:
        st.session_state["q_start_time"] = time.time()

    elapsed   = elapsed_seconds()
    remaining = max(0.0, time_limit - elapsed)
    timer_cls = "timer-value warning" if remaining < 20 else "timer-value"

    col_timer, _ = st.columns([1, 3])
    with col_timer:
        st.markdown(
            f'<div class="timer-wrap">'
            f'<div class="timer-label">⏱ Time Remaining</div>'
            f'<div class="{timer_cls}">{int(remaining)}s</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Question card ─────────────────────────
    diff_tag_cls = {
        "Easy": "tag-diff-easy", "Medium": "tag-diff-medium", "Hard": "tag-diff-hard"
    }.get(question.get("difficulty", "Easy"), "tag")

    st.markdown(
        f'<div class="q-card">'
        f'<div class="q-meta">'
        f'<span class="tag {diff_tag_cls}">{html_lib.escape(question.get("difficulty","Easy"))}</span>'
        f'<span class="tag">{html_lib.escape(question.get("type","Technical").title())}</span>'
        f'<span class="tag">{html_lib.escape(question.get("skill_tag","General"))}</span>'
        f'<span class="tag">Q{q_idx + 1}/{TOTAL_QUESTIONS}</span>'
        f'</div>'
        f'<div class="q-text">{html_lib.escape(question.get("text",""))}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Answer input ──────────────────────────
    answer_txt = st.text_area(
        label="Your Answer",
        placeholder="Type your answer here… Be clear, specific, and concise.",
        height=180,
        key=f"answer_input_{q_idx}",
        label_visibility="collapsed",
    )

    btn_col, skip_col, _ = st.columns([1, 1, 3], gap="small")
    with btn_col:
        submit = st.button("✅ Submit Answer", key=f"submit_{q_idx}", use_container_width=True)
    with skip_col:
        skip = st.button("⏭ Skip / Time Out", key=f"skip_{q_idx}", use_container_width=True)

    # ── Handle manual submission or skip ──────
    if submit or skip:
        actual_answer  = answer_txt.strip() if (submit and answer_txt.strip()) else ""
        actual_elapsed = elapsed_seconds()
        _submit_answer(q_idx, question, actual_answer, actual_elapsed)
        return

    # ── Auto-timeout (fires because autorefresh reruns every 3 s) ──
    if remaining <= 0 and not st.session_state.get("_show_feedback"):
        st.warning("⏰ Time's up! Auto-submitting…")
        _submit_answer(q_idx, question, "", elapsed_seconds())


def _submit_answer(q_idx: int, question: dict, answer_text: str, time_taken: float):
    """Evaluate one answer, update streak + difficulty, set feedback state."""
    with st.spinner("Evaluating answer…"):
        try:
            result = evaluate_answer(
                question       = question,
                answer_text    = answer_text,
                time_taken     = time_taken,
                resume_context = st.session_state.get("resume_text", "")[:800],
                jd_context     = st.session_state.get("jd_text", "")[:500],
            )
        except Exception as e:
            st.error(f"Evaluation failed: {e}")
            st.stop()

    st.session_state["scores"].append(result)
    st.session_state["answers"].append({
        "q_index":    q_idx,
        "text":       answer_text,
        "time_taken": time_taken,
    })

    if result["weighted_score"] < POOR_ANSWER_THRESHOLD:
        st.session_state["poor_streak"] += 1
    else:
        st.session_state["poor_streak"] = 0

    adjust_difficulty(result["weighted_score"])

    st.session_state["_last_eval"]     = result
    st.session_state["_show_feedback"] = True
    st.rerun()


def _render_feedback_and_advance(question: dict, time_limit: int):
    """Show per-question feedback, then advance or end the interview."""
    result      = st.session_state["_last_eval"]
    score       = result["weighted_score"]
    score_color = "#4ade80" if score >= 7 else ("#f0c04a" if score >= 4 else "#f87171")
    dims        = ["accuracy", "clarity", "depth", "relevance", "time_efficiency"]

    st.markdown(
        '<h2 style="font-family:Syne,sans-serif;font-size:1.4rem;'
        'font-weight:700;color:#e8e9ed;margin-bottom:1rem;">Answer Feedback</h2>',
        unsafe_allow_html=True,
    )

    fb_col, dim_col = st.columns([1, 1], gap="large")

    with fb_col:
        # FIX 5: escape gemini_feedback before HTML injection
        safe_feedback = html_lib.escape(result["gemini_feedback"])
        st.markdown(
            f'<div class="feedback-card">'
            f'<div class="feedback-label">Weighted Score</div>'
            f'<div class="feedback-score" style="color:{score_color};">'
            f'{score:.1f}<span style="font-size:1rem;color:#5a6080;">/10</span></div>'
            f'<div class="feedback-text">{safe_feedback}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with dim_col:
        rows_html = "".join(
            f'<div class="dim-row">'
            f'<span class="dim-name">{d.replace("_"," ").title()}</span>'
            f'<span class="dim-score">{result[d]:.1f}</span>'
            f'</div>'
            for d in dims
        )
        st.markdown(
            f'<div class="feedback-card">'
            f'<div class="feedback-label">Dimension Breakdown</div>'
            f'{rows_html}'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Difficulty change notice
    new_diff = st.session_state["difficulty"]
    old_diff = question.get("difficulty", "Easy")
    if new_diff != old_diff:
        direction = (
            "harder"
            if DIFFICULTY_LEVELS.index(new_diff) > DIFFICULTY_LEVELS.index(old_diff)
            else "easier"
        )
        st.markdown(
            f'<div style="background:#1e1a08;border:1px solid #7a5c10;border-radius:8px;'
            f'padding:0.75rem 1rem;margin-top:0.75rem;font-size:0.82rem;color:#f0c04a;">'
            f'🔄 Difficulty adjusted to <strong>{new_diff}</strong> ({direction})</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    q_idx           = st.session_state["current_q_index"]
    early_terminate = check_early_termination()
    last_question   = (q_idx + 1) >= TOTAL_QUESTIONS

    if early_terminate:
        st.markdown(
            '<div class="terminated-banner">'
            '🛑 <strong>Early termination triggered.</strong> '
            '3 consecutive low-scoring answers detected. Generating your report…'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("📊 View Report", key="view_report_early", use_container_width=False):
            _finalise_interview(STAGE_TERMINATED)
    elif last_question:
        st.success("🎉 Interview complete! All questions answered.")
        if st.button("📊 View Final Report", key="view_report_final", use_container_width=False):
            _finalise_interview(STAGE_RESULTS)
    else:
        if st.button("➡ Next Question", key="next_q", use_container_width=False):
            st.session_state["current_q_index"] += 1
            st.session_state["_show_feedback"]  = False
            st.session_state["_last_eval"]      = None
            st.session_state["q_start_time"]    = time.time()
            st.rerun()


def _finalise_interview(target_stage: str):
    """Generate the report and transition to the results stage."""
    with st.spinner("Generating your Interview Readiness Report…"):
        try:
            report = generate_report(
                scores     = st.session_state["scores"],
                skill_gaps = st.session_state["skill_gaps"],
                jd_text    = st.session_state.get("jd_text", ""),
                stage      = target_stage,
            )
        except Exception as e:
            # FIX 4: clear feedback lock before stopping so the user
            # is not trapped on the feedback screen after a crash.
            st.session_state["_show_feedback"] = False
            st.error(f"Report generation failed: {e}")
            st.stop()

    st.session_state["report"] = report
    st.session_state["stage"]  = target_stage
    st.rerun()


# ══════════════════════════════════════════════
#  STAGE: RESULTS
# ══════════════════════════════════════════════

def render_results():
    report     = st.session_state.get("report", {})
    stage      = st.session_state["stage"]
    terminated = stage == STAGE_TERMINATED

    if not report:
        st.error("No report found. Please complete an interview first.")
        if st.button("↩ Back to Setup"):
            st.session_state["stage"] = STAGE_SETUP
            st.rerun()
        return

    final_score = report["final_score"]
    band        = report["band"]
    hire_ok     = report["hire_recommended"]

    band_cls   = {"Strong": "band-strong", "Average": "band-average"}.get(band, "band-weak")
    hire_cls   = "hire-yes" if hire_ok else "hire-no"
    hire_label = "✅ Hire Recommended" if hire_ok else "❌ Not Ready — Continue Preparing"

    if terminated and report.get("termination_reason"):
        st.markdown(
            f'<div class="terminated-banner">'
            f'🛑 {html_lib.escape(report["termination_reason"])}'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="report-hero">'
        f'<div style="font-size:0.75rem;color:#5a6080;text-transform:uppercase;'
        f'letter-spacing:0.15em;margin-bottom:0.5rem;">Interview Readiness Score</div>'
        f'<div class="report-score-big">{final_score:.1f}</div>'
        f'<div style="color:#3a4060;font-size:0.85rem;">/ 100</div>'
        f'<div class="report-band {band_cls}">{html_lib.escape(band)}</div>'
        f'<div><span class="hire-badge {hire_cls}">{hire_label}</span></div>'
        f'<div style="margin-top:1rem;font-size:0.78rem;color:#3a4060;">'
        f'{report["questions_attempted"]} question'
        f'{"s" if report["questions_attempted"] != 1 else ""} answered'
        f' &nbsp;·&nbsp; Completion: {report.get("completion_ratio", 0) * 100:.0f}%'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Two-column breakdown ───────────────────
    col_l, col_r = st.columns([1, 1], gap="large")

    with col_l:
        dim_avgs = report.get("dimension_averages", {})
        if dim_avgs:
            st.markdown('<div class="section-title">📐 Scoring Dimensions</div>', unsafe_allow_html=True)
            rows = ""
            for d, v in dim_avgs.items():
                color = "#4ade80" if v >= 7 else ("#f0c04a" if v >= 4 else "#f87171")
                rows += (
                    f'<div class="dim-row">'
                    f'<span class="dim-name">{d.replace("_"," ").title()}</span>'
                    f'<span class="dim-score" style="color:{color};">{v:.1f}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="feedback-card" style="margin-bottom:1.5rem;">{rows}</div>',
                unsafe_allow_html=True,
            )

        skill_scores = report.get("skill_scores", {})
        if skill_scores:
            st.markdown('<div class="section-title">🎯 Skill Performance</div>', unsafe_allow_html=True)
            rows = ""
            for skill, v in sorted(skill_scores.items(), key=lambda x: -x[1]):
                color = "#4ade80" if v >= 7 else ("#f0c04a" if v >= 4 else "#f87171")
                rows += (
                    f'<div class="dim-row">'
                    f'<span class="dim-name">{html_lib.escape(skill)}</span>'
                    f'<span class="dim-score" style="color:{color};">{v:.1f}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div class="feedback-card" style="margin-bottom:1.5rem;">{rows}</div>',
                unsafe_allow_html=True,
            )

    with col_r:
        strengths = report.get("strengths", [])
        if strengths:
            st.markdown('<div class="section-title">💪 Strengths</div>', unsafe_allow_html=True)
            st.markdown(
                " ".join(
                    f'<span class="skill-pill skill-strong">{html_lib.escape(s)}</span>'
                    for s in strengths
                ),
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

        weaknesses = report.get("weaknesses", [])
        if weaknesses:
            st.markdown('<div class="section-title">⚠️ Areas to Improve</div>', unsafe_allow_html=True)
            st.markdown(
                " ".join(
                    f'<span class="skill-pill skill-weak">{html_lib.escape(w)}</span>'
                    for w in weaknesses
                ),
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

        gaps = st.session_state.get("skill_gaps", [])
        if gaps:
            st.markdown('<div class="section-title">🔍 JD Skill Gaps</div>', unsafe_allow_html=True)
            st.markdown(
                " ".join(
                    f'<span class="skill-pill skill-gap">{html_lib.escape(g)}</span>'
                    for g in gaps
                ),
                unsafe_allow_html=True,
            )
            st.markdown("<br>", unsafe_allow_html=True)

    # ── Improvement tips ──────────────────────
    tips = report.get("improvement_tips", [])
    if tips:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(
            '<h2 style="font-family:Syne,sans-serif;font-size:1.2rem;'
            'font-weight:700;color:#e8e9ed;margin-bottom:1rem;">'
            '📚 Personalised Improvement Tips</h2>',
            unsafe_allow_html=True,
        )
        for tip in tips:
            # FIX 5: escape tip text before HTML injection
            st.markdown(
                f'<div class="tip-card">💡 {html_lib.escape(tip)}</div>',
                unsafe_allow_html=True,
            )

    # ── Per-question log ──────────────────────
    with st.expander("📋 Full Question-by-Question Log", expanded=False):
        for i, (q, s) in enumerate(
            zip(st.session_state["questions"], st.session_state["scores"])
        ):
            ans = next(
                (a["text"] for a in st.session_state["answers"] if a["q_index"] == i),
                "[no answer]",
            )
            score_color = (
                "#4ade80" if s["weighted_score"] >= 7
                else ("#f0c04a" if s["weighted_score"] >= 4 else "#f87171")
            )
            # FIX 5: escape all Gemini-sourced text before HTML injection
            safe_q_text  = html_lib.escape(q.get("text", ""))
            safe_ans     = html_lib.escape(ans[:300])
            safe_fb      = html_lib.escape(s["gemini_feedback"])
            safe_diff    = html_lib.escape(s["difficulty"])
            safe_skill   = html_lib.escape(s["skill_tag"])

            st.markdown(
                f'<div style="background:#13161d;border:1px solid #1f2330;'
                f'border-radius:10px;padding:1rem 1.25rem;margin-bottom:0.75rem;">'
                f'<div style="font-size:0.72rem;color:#5a6080;margin-bottom:0.4rem;">'
                f'Q{i+1} · {safe_diff} · {safe_skill}'
                f'&nbsp;&nbsp;<span style="color:{score_color};font-weight:700;">'
                f'{s["weighted_score"]:.1f}/10</span></div>'
                f'<div style="font-size:0.85rem;color:#e8e9ed;margin-bottom:0.5rem;">{safe_q_text}</div>'
                f'<div style="font-size:0.8rem;color:#9aa0b8;font-style:italic;margin-bottom:0.4rem;">'
                f'{safe_ans}{"…" if len(ans) > 300 else ""}</div>'
                f'<div style="font-size:0.78rem;color:#5a6080;">{safe_fb}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Actions ───────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    act_col1, act_col2, _ = st.columns([1, 1, 2], gap="small")
    with act_col1:
        if st.button("🔄 New Interview", key="restart", use_container_width=True):
            for k in ("current_q_index", "poor_streak", "questions", "answers",
                      "scores", "report", "q_start_time", "interview_start_time",
                      "_show_feedback", "_last_eval"):
                st.session_state[k] = (
                    0   if k in ("current_q_index", "poor_streak") else
                    []  if k in ("questions", "answers", "scores") else
                    None
                )
            st.session_state["difficulty"] = STARTING_DIFFICULTY
            st.session_state["stage"]      = STAGE_SETUP
            st.rerun()
    with act_col2:
        if st.button("↩ Back to Setup", key="back_setup", use_container_width=True):
            st.session_state["stage"] = STAGE_SETUP
            st.rerun()


# ══════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════

render_sidebar()

stage = st.session_state["stage"]

if stage == STAGE_SETUP:
    render_setup()

elif stage == STAGE_READY:
    # Transient state: move straight into the interview
    st.session_state["stage"]                = STAGE_INTERVIEW
    st.session_state["interview_start_time"] = time.time()
    st.rerun()

elif stage == STAGE_INTERVIEW:
    render_interview()

elif stage in (STAGE_TERMINATED, STAGE_RESULTS):
    render_results()

else:
    st.error(f"Unknown stage: {stage}")
    st.session_state["stage"] = STAGE_SETUP
    st.rerun()