"""Resume Designer agent for creating optimized, standout resumes."""

from google.adk import Agent
from google.adk.tools import google_search

from . import prompt

MODEL = "gemini-2.5-pro"

resume_designer_agent = Agent(
    model=MODEL,
    name="resume_designer_agent",
    description=(
        "Creates compelling, ATS-optimized resumes tailored to specific roles "
        "and job postings. Focuses on quantifiable achievements, keyword "
        "optimization, and creating a standout narrative that appeals to both "
        "automated systems and human reviewers."
    ),
    instruction=prompt.RESUME_DESIGNER_PROMPT,
    output_key="resume_design_output",
    tools=[google_search],
)

