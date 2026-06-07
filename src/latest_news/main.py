#!/usr/bin/env python
import sys
import warnings

from latest_news.flow import NewsReporterFlow

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run():
    """Run the News Reporter Flow."""
    topic = sys.argv[1] if len(sys.argv) > 1 else "Artificial Intelligence"

    flow = NewsReporterFlow()
    flow.state.topic = topic
    flow.kickoff()


def train():
    """Train the underlying crew for a given number of iterations."""
    from latest_news.crew import NewsReporterCrew

    inputs = {"topic": sys.argv[3] if len(sys.argv) > 3 else "Artificial Intelligence"}
    try:
        NewsReporterCrew().crew().train(
            n_iterations=int(sys.argv[1]),
            filename=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """Replay the crew execution from a specific task."""
    from latest_news.crew import NewsReporterCrew

    try:
        NewsReporterCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """Test the crew execution and return results."""
    from latest_news.crew import NewsReporterCrew

    inputs = {"topic": "Artificial Intelligence"}
    try:
        NewsReporterCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            eval_llm=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_app():
    """Launch the Streamlit UI."""
    import subprocess
    import os

    app_path = os.path.join(os.path.dirname(__file__), "app.py")
    subprocess.run(["streamlit", "run", app_path], check=True)


def run_with_trigger():
    """Run the flow with a JSON trigger payload."""
    import json

    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide a JSON payload as argument.")

    try:
        trigger_payload = json.loads(sys.argv[1])
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument.")

    topic = trigger_payload.get("topic", "Artificial Intelligence")

    flow = NewsReporterFlow()
    flow.state.topic = topic
    return flow.kickoff()