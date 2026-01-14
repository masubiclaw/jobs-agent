"""Job Searcher agent for finding and aggregating job listings."""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro"

job_searcher_agent = Agent(
    model=MODEL,
    name="job_searcher_agent",
    description=(
        "Searches for job listings across multiple platforms including LinkedIn, "
        "Indeed, Glassdoor, and company career pages. Aggregates results, removes "
        "duplicates, and ranks matches based on candidate profile alignment and "
        "job quality indicators."
    ),
    instruction=prompt.JOB_SEARCHER_PROMPT,
    output_key="job_search_output",
    tools=[google_search],
)

