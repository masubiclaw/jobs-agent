"""Job Posting Analyst agent for deep analysis of job postings."""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro"

job_posting_analyst_agent = Agent(
    model=MODEL,
    name="job_posting_analyst_agent",
    description=(
        "Provides deep analysis of job postings including requirements breakdown, "
        "keyword extraction, culture assessment, red flag detection, and profile "
        "matching. Researches companies and provides honest assessments with "
        "actionable application strategies."
    ),
    instruction=prompt.JOB_POSTING_ANALYST_PROMPT,
    output_key="job_posting_analysis_output",
    tools=[google_search],
)

