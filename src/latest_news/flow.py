from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel

from latest_news.crew import NewsReporterCrew


class NewsState(BaseModel):
    topic: str = ""
    article: str = ""


class NewsReporterFlow(Flow[NewsState]):
    """
    News Reporter Flow

    Pipeline:
        1. Manager     — defines the editorial scope and research brief
        2. News Hunter — searches the internet for the latest news
        3. Fact Checker — verifies every claim and removes unverified content
        4. Editor      — writes the final publication-ready article
    """

    @start()
    def start_pipeline(self):
        print(f"\n{'='*60}")
        print(f"News Reporter Pipeline started")
        print(f"Topic: {self.state.topic}")
        print(f"{'='*60}\n")

    @listen(start_pipeline)
    def run_news_crew(self):
        result = NewsReporterCrew().crew().kickoff(
            inputs={"topic": self.state.topic}
        )
        self.state.article = result.raw
        return result.raw

    @listen(run_news_crew)
    def publish_article(self, article: str):
        print(f"\n{'='*60}")
        print("Final article saved to: output/news_article.md")
        print(f"{'='*60}\n")
        return article


def kickoff(topic: str = "Artificial Intelligence"):
    flow = NewsReporterFlow()
    flow.state.topic = topic
    return flow.kickoff()