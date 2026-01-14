"""Company Researcher Agent: Researches companies for ratings, reviews, culture, and values."""

from google.adk.agents import Agent
from google.adk.tools import google_search

from .prompt import COMPANY_RESEARCHER_PROMPT

# Import MCP tools - will be None if APIFY_API_TOKEN not set
try:
    from ...tools.mcp_tools import (
        get_glassdoor_company_mcp,
        get_glassdoor_company_search_mcp,
    )
    glassdoor_company_mcp = get_glassdoor_company_mcp()
    glassdoor_company_search_mcp = get_glassdoor_company_search_mcp()
except ImportError:
    glassdoor_company_mcp = None
    glassdoor_company_search_mcp = None

# Build tools list
company_research_tools = [google_search]
if glassdoor_company_mcp:
    company_research_tools.append(glassdoor_company_mcp)
if glassdoor_company_search_mcp:
    company_research_tools.append(glassdoor_company_search_mcp)

company_researcher_agent = Agent(
    model="gemini-2.5-flash",
    name="company_researcher_agent",
    description=(
        "Researches companies using Glassdoor MCP and web search for ratings, "
        "reviews, culture, values, and employee insights"
    ),
    instruction=COMPANY_RESEARCHER_PROMPT,
    output_key="company_research_results",
    tools=company_research_tools,
)

