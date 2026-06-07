"""Streamlit UI for the News Reporter pipeline."""

import os
import threading
import time
from datetime import datetime, timedelta

import streamlit as st

from latest_news.database import (
    complete_session,
    create_session,
    delete_session,
    get_comments,
    get_session_outputs,
    init_db,
    list_sessions,
    save_comment,
    save_output,
)

STAGES = [
    ("brief",    "Editorial Brief"),
    ("raw",      "Raw News"),
    ("verified", "Verified News"),
    ("article",  "Final Article"),
]

STAGE_LABELS = {
    "brief":    "Defining topic scope",
    "raw":      "Hunting for news",
    "verified": "Fact-checking",
    "article":  "Writing article",
}

OUTPUT_FILES = {
    "brief":    "output/1_editorial_brief.md",
    "raw":      "output/2_raw_news.md",
    "verified": "output/3_verified_news.md",
    "article":  "output/news_article.md",
}

# --- CSS ---

SPINNER_CSS = """
<style>
@keyframes spin { to { transform: rotate(360deg); } }

.stage-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    border-radius: 8px;
    margin-bottom: 6px;
    font-size: 15px;
}
.stage-done   { background: #1a3a2a; color: #4ade80; }
.stage-active { background: #1a2a3a; color: #60a5fa; }
.stage-pending{ background: #1a1a1a; color: #6b7280; }

.spinner {
    width: 18px; height: 18px;
    border: 2.5px solid #60a5fa44;
    border-top-color: #60a5fa;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    flex-shrink: 0;
}
.check  { font-size: 16px; flex-shrink: 0; }
.dot    { width: 18px; height: 18px; display:flex; align-items:center;
          justify-content:center; flex-shrink:0; color:#6b7280; font-size:18px; }
</style>
"""


def _stage_html(stage: str, label: str, state: str) -> str:
    """state: done | active | pending"""
    if state == "done":
        icon = '<span class="check">✅</span>'
        cls = "stage-done"
    elif state == "active":
        icon = '<div class="spinner"></div>'
        cls = "stage-active"
    else:
        icon = '<div class="dot">◦</div>'
        cls = "stage-pending"
    return f'<div class="stage-row {cls}">{icon}<span>{label}</span></div>'


# --- background crew runner ---

def _clear_output_files():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for filepath in OUTPUT_FILES.values():
        p = os.path.join(base, filepath)
        if os.path.exists(p):
            os.remove(p)


def _watch_stages(session_id: int, status_list: list, stop_event: threading.Event, run_start: float):
    seen = set()
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    while not stop_event.is_set():
        for stage, filepath in OUTPUT_FILES.items():
            if stage in seen:
                continue
            p = os.path.join(base, filepath)
            if os.path.exists(p) and os.path.getsize(p) > 0 and os.path.getmtime(p) >= run_start:
                with open(p, encoding="utf-8") as f:
                    save_output(session_id, stage, f.read())
                status_list.append(f"__STAGE__{stage}")
                seen.add(stage)
        time.sleep(1)


def _run_crew(topic: str, session_id: int, status_list: list):
    from latest_news.crew import NewsReporterCrew

    _clear_output_files()
    run_start = time.time()

    stop_event = threading.Event()
    threading.Thread(
        target=_watch_stages,
        args=(session_id, status_list, stop_event, run_start),
        daemon=True,
    ).start()

    try:
        cutoff = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        NewsReporterCrew().crew().kickoff(inputs={"topic": topic, "cutoff_date": cutoff})
        complete_session(session_id, "completed")
        status_list.append("__DONE__")
    except Exception as exc:
        complete_session(session_id, "failed")
        status_list.append(f"__ERROR__ {exc}")
    finally:
        stop_event.set()


# --- Q&A ---

def _ask_editor(article: str, question: str) -> str:
    from crewai import Agent, Crew, Process, Task

    editor = Agent(
        role="News Editor",
        goal="Answer questions about the provided news article accurately.",
        backstory="You are an expert news editor. You only use the article text provided — no internet searches.",
        verbose=False,
        respect_context_window=True,
    )
    task = Task(
        description=(
            f"Using ONLY the article below, answer this question: {question}\n\n"
            f"---\n{article}\n---\n\n"
            "Do not search the internet. Base your answer solely on the article."
        ),
        expected_output="A clear, concise answer based only on the article content.",
        agent=editor,
    )
    result = Crew(agents=[editor], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    return result.raw


# --- sidebar ---

def sidebar():
    st.sidebar.title("📰 News Reporter")
    st.sidebar.caption("Session history")

    sessions = list_sessions()
    if not sessions:
        st.sidebar.info("No sessions yet.")
        return None

    selected_id = None
    for s in sessions:
        ts = s["timestamp"].strftime("%b %d %H:%M") if s["timestamp"] else "—"
        icon = {"completed": "✅", "running": "⏳", "failed": "❌"}.get(s["status"], "?")
        col1, col2 = st.sidebar.columns([5, 1])
        with col1:
            label = f"{icon} {s['topic'][:30]}  ·  {ts}"
            if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
                selected_id = s["id"]
        with col2:
            if st.button("🗑", key=f"del_{s['id']}", help="Delete session"):
                delete_session(s["id"])
                if st.session_state.get("view_session") == s["id"]:
                    st.session_state["view_session"] = None
                st.rerun()

    return selected_id


# --- session detail ---

def session_detail(session_id: int):
    sessions = list_sessions()
    session = next((s for s in sessions if s["id"] == session_id), None)
    if not session:
        st.error("Session not found.")
        return

    ts = session["timestamp"].strftime("%Y-%m-%d %H:%M") if session["timestamp"] else "—"
    st.caption(f"Run at {ts}  ·  Status: {session['status']}")

    outputs = get_session_outputs(session_id)
    if not outputs:
        st.warning("No outputs saved for this session.")
        return

    if "article" in outputs:
        st.markdown(outputs["article"])
        st.divider()

    with st.expander("Show intermediate stages"):
        for stage, label in STAGES[:-1]:
            if stage in outputs:
                st.subheader(label)
                st.markdown(outputs[stage])
                st.divider()

    st.subheader("Ask about this article")
    article_text = outputs.get("article", "")

    for c in get_comments(session_id):
        with st.chat_message("user"):
            st.write(c["question"])
        with st.chat_message("assistant"):
            st.write(c["answer"])

    question = st.chat_input("Ask a question about this article…")
    if question and article_text:
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                answer = _ask_editor(article_text, question)
            st.write(answer)
            save_comment(session_id, question, answer)


# --- new run page ---

def new_run_page():
    st.title("Run New Topic")

    topic = st.text_input(
        "Topic",
        placeholder="e.g. Bitcoin ETF, Climate Change, AI regulation",
        key="topic_input",
    )

    if st.button("Run Pipeline", type="primary", disabled=not topic.strip()):
        st.session_state["running"] = True
        st.session_state["status_list"] = []
        st.session_state["run_topic"] = topic.strip()
        st.session_state["run_session_id"] = create_session(topic.strip())

        threading.Thread(
            target=_run_crew,
            args=(
                st.session_state["run_topic"],
                st.session_state["run_session_id"],
                st.session_state["status_list"],
            ),
            daemon=True,
        ).start()
        st.rerun()

    if st.session_state.get("running"):
        status_list: list = st.session_state.get("status_list", [])
        topic_running = st.session_state["run_topic"]

        st.subheader(f"Running pipeline for: **{topic_running}**")
        st.markdown(SPINNER_CSS, unsafe_allow_html=True)

        completed_stages = {s.replace("__STAGE__", "") for s in status_list if s.startswith("__STAGE__")}
        done = "__DONE__" in status_list
        error = next((s for s in status_list if s.startswith("__ERROR__")), None)

        active_shown = False
        html_rows = ""
        for stage, label in STAGES:
            if stage in completed_stages:
                html_rows += _stage_html(stage, label, "done")
            elif not done and not error and not active_shown:
                html_rows += _stage_html(stage, f"{label} — {STAGE_LABELS[stage]}...", "active")
                active_shown = True
            else:
                html_rows += _stage_html(stage, label, "pending")

        st.markdown(html_rows, unsafe_allow_html=True)

        if done:
            st.success("Pipeline complete!")
            st.session_state["running"] = False
            st.session_state["view_session"] = st.session_state["run_session_id"]
            time.sleep(0.5)
            st.rerun()
        elif error:
            st.error(error.replace("__ERROR__ ", ""))
            st.session_state["running"] = False
        else:
            time.sleep(2)
            st.rerun()


# --- main ---

def main():
    st.set_page_config(
        page_title="News Reporter",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_db()

    if "running" not in st.session_state:
        st.session_state["running"] = False
    if "view_session" not in st.session_state:
        st.session_state["view_session"] = None

    selected_from_sidebar = sidebar()
    if selected_from_sidebar:
        st.session_state["view_session"] = selected_from_sidebar

    if st.session_state["view_session"] and not st.session_state["running"]:
        sessions = list_sessions()
        session = next((s for s in sessions if s["id"] == st.session_state["view_session"]), None)

        col1, col2, col3 = st.columns([7, 1, 1])
        with col1:
            if session:
                st.title(session["topic"])
        with col2:
            if session and st.button("🗑 Delete", type="secondary"):
                delete_session(session["id"])
                st.session_state["view_session"] = None
                st.rerun()
        with col3:
            if st.button("← New Run"):
                st.session_state["view_session"] = None
                st.rerun()

        session_detail(st.session_state["view_session"])
    else:
        new_run_page()


if __name__ == "__main__":
    main()