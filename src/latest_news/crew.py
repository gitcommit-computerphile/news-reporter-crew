from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.memory.unified_memory import Memory
from crewai_tools import SerperDevTool


@CrewBase
class NewsReporterCrew:
    """News Reporter Crew — four-agent pipeline: Manager, News Hunter, Fact Checker, Editor."""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- Agents ---

    @agent
    def manager(self) -> Agent:
        return Agent(
            config=self.agents_config["manager"],  # type: ignore[index]
            verbose=True,
            respect_context_window=True,
        )

    @agent
    def news_hunter(self) -> Agent:
        return Agent(
            config=self.agents_config["news_hunter"],  # type: ignore[index]
            tools=[SerperDevTool(tbs="qdr:m6")],
            verbose=True,
            respect_context_window=True,
            max_iter=3,
        )

    @agent
    def fact_checker(self) -> Agent:
        return Agent(
            config=self.agents_config["fact_checker"],  # type: ignore[index]
            tools=[SerperDevTool(tbs="qdr:m6")],
            verbose=True,
            respect_context_window=True,
            max_iter=3,
        )

    @agent
    def editor(self) -> Agent:
        return Agent(
            config=self.agents_config["editor"],  # type: ignore[index]
            verbose=True,
            respect_context_window=True,
        )

    # --- Tasks ---

    @task
    def topic_definition_task(self) -> Task:
        return Task(
            config=self.tasks_config["topic_definition_task"],  # type: ignore[index]
        )

    @task
    def news_hunting_task(self) -> Task:
        return Task(
            config=self.tasks_config["news_hunting_task"],  # type: ignore[index]
            context=[self.topic_definition_task()],
        )

    @task
    def fact_checking_task(self) -> Task:
        return Task(
            config=self.tasks_config["fact_checking_task"],  # type: ignore[index]
            context=[self.topic_definition_task(), self.news_hunting_task()],
        )

    @task
    def article_writing_task(self) -> Task:
        return Task(
            config=self.tasks_config["article_writing_task"],  # type: ignore[index]
            context=[
                self.topic_definition_task(),
                self.news_hunting_task(),
                self.fact_checking_task(),
            ],
        )

    # --- Crew ---

    @crew
    def crew(self) -> Crew:
        """Creates the News Reporter Crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            max_rpm=5,
            respect_context_window=True,
            memory=Memory(
                llm="gpt-5.4-mini",
                embedder={
                    "provider": "openai",
                    "config": {"model": "text-embedding-3-small"},
                },
            ),
        )