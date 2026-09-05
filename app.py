"""Streamlit UI for cv-screener: paste or upload a CV, run the agent, review the scorecard."""
import contextlib
import io
import os

import streamlit as st
from dotenv import load_dotenv

from guardrails import ScreeningOutcome
from main import MAX_TOOL_CALLS, MODEL, screen_cv

load_dotenv()

st.set_page_config(page_title="CV Screener", page_icon="\U0001F4CB", layout="wide")

RESULT_BADGES = {
    "ok": ("✅", "green"),
    "blocked": ("⛔", "red"),
    "incomplete": ("⏸️", "orange"),
}

RECOMMENDATION_COLORS = {
    "advance": "green",
    "hold": "orange",
    "reject": "red",
}

RESULT_ICONS = {
    "meets": "✅",
    "partially meets": "⚠️",
    "fails": "❌",
}


def _run_screening(cv_text: str) -> tuple[ScreeningOutcome | None, str, Exception | None]:
    """Run screen_cv, capturing its stdout trace so it can be shown in the UI."""
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            outcome = screen_cv(cv_text)
        return outcome, buffer.getvalue(), None
    except Exception as exc:  # surfaced to the user instead of crashing the app
        return None, buffer.getvalue(), exc


def _render_scorecard(outcome: ScreeningOutcome) -> None:
    badge, color = RESULT_BADGES.get(outcome.status, ("❓", "gray"))
    st.markdown(f"### {badge} Status: `:{color}[{outcome.status}]`")

    if outcome.requires_human_review:
        st.warning("This result requires human review before any action is taken.")

    if outcome.message:
        st.info(outcome.message)

    if outcome.scorecard is None:
        return

    sc = outcome.scorecard
    rec_color = RECOMMENDATION_COLORS.get(sc.recommendation, "gray")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Score", f"{sc.score}/100")
        st.markdown(f"**Recommendation:** :{rec_color}[{sc.recommendation.upper()}]")
    with col2:
        st.markdown("**Summary**")
        st.write(sc.summary)

    st.markdown("---")
    st.markdown("**Findings**")
    for finding in sc.findings:
        icon = RESULT_ICONS.get(finding.result, "")
        criterion_label = finding.criterion.replace("_", " ").title()
        with st.container(border=True):
            header = f"{icon} **{criterion_label}** — {finding.result}"
            if finding.is_critical:
                header += " :red[(critical)]"
            st.markdown(header)
            st.write(finding.detail)
            if finding.recruiter_note:
                st.caption(f"Recruiter note (internal, proposal only): {finding.recruiter_note}")


st.title("\U0001F4CB CV Screener")
st.caption("BGO call center agent fitness screening")

with st.sidebar:
    st.subheader("Configuration")
    st.write(f"**Model:** `{MODEL}`")
    st.write(f"**Max tool calls:** {MAX_TOOL_CALLS}")
    if os.environ.get("GEMINI_API_KEY"):
        st.success("GEMINI_API_KEY is set")
    else:
        st.error("GEMINI_API_KEY is not set — screening calls will fail.")
    st.markdown("---")
    st.caption(
        "Runs are reported to Spine Central if SPINE_CENTRAL_URL is configured; "
        "otherwise reporting is a no-op."
    )

input_mode = st.radio("CV input", ["Paste text", "Upload file"], horizontal=True)

cv_text = ""
if input_mode == "Paste text":
    cv_text = st.text_area("Candidate CV text", height=300, placeholder="Paste the CV text here...")
else:
    uploaded = st.file_uploader("Upload a plain-text CV file", type=["txt", "md"])
    if uploaded is not None:
        cv_text = uploaded.read().decode("utf-8")
        st.text_area("Preview", value=cv_text, height=300, disabled=True)

run = st.button("Screen CV", type="primary", disabled=not cv_text.strip())

if run:
    with st.spinner("Running the screening agent..."):
        outcome, trace, error = _run_screening(cv_text)

    if error is not None:
        st.error(f"Screening failed: {error}")
    else:
        _render_scorecard(outcome)

    if trace.strip():
        with st.expander("Agent trace (model turns, tool calls, guardrail checks)"):
            st.code(trace, language=None)
