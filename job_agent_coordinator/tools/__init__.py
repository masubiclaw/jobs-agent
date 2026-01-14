"""Tools for the job search agent."""

from .mcp_tools import (
    # Apify MCP (unified)
    get_apify_mcp,
    # Glassdoor
    get_glassdoor_tools,
    get_glassdoor_jobs_mcp,
    get_glassdoor_company_mcp,
    get_glassdoor_company_search_mcp,
    # Indeed
    get_indeed_tools,
    get_indeed_jobs_mcp,
    get_indeed_company_mcp,
    # Multi-platform
    get_jobspy_mcp,
    get_all_job_platform_tools,
)

from .pdf_tools import (
    # PDF Generation
    generate_resume_pdf,
    generate_cover_letter_pdf,
    generate_resume_pdf_tool,
    generate_cover_letter_pdf_tool,
    list_generated_pdfs,
    delete_pdf,
    is_pdf_generation_available,
    get_resume_template_presets,
    get_output_directory,
)

__all__ = [
    # Apify MCP (unified)
    "get_apify_mcp",
    # Glassdoor
    "get_glassdoor_tools",
    "get_glassdoor_jobs_mcp",
    "get_glassdoor_company_mcp",
    "get_glassdoor_company_search_mcp",
    # Indeed
    "get_indeed_tools",
    "get_indeed_jobs_mcp",
    "get_indeed_company_mcp",
    # Multi-platform
    "get_jobspy_mcp",
    "get_all_job_platform_tools",
    # PDF Generation
    "generate_resume_pdf",
    "generate_cover_letter_pdf",
    "generate_resume_pdf_tool",
    "generate_cover_letter_pdf_tool",
    "list_generated_pdfs",
    "delete_pdf",
    "is_pdf_generation_available",
    "get_resume_template_presets",
    "get_output_directory",
]
