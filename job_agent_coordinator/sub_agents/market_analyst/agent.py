"""Market Analyst agent for job market intelligence and trends."""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro"

market_analyst_agent = Agent(
    model=MODEL,
    name="market_analyst_agent",
    description=(
        "Provides comprehensive job market intelligence including demand analysis, "
        "salary insights, skill trends, industry outlook, and strategic career "
        "recommendations. Uses multiple data sources to validate trends and "
        "provide actionable market positioning advice."
    ),
    instruction=prompt.MARKET_ANALYST_PROMPT,
    output_key="market_analysis_output",
    tools=[google_search],
)

