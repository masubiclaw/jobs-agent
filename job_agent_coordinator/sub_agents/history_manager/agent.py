"""History Manager Agent: Stores and retrieves job search history using vector database."""

import json
from typing import Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from .prompt import HISTORY_MANAGER_PROMPT
from .vector_store import get_vector_store
from ...logging_config import log_agent_call, history_logger

MODEL = "gemini-2.5-flash"


# =============================================================================
# History Tools - Exposed as FunctionTools for the agent
# =============================================================================

@log_agent_call(history_logger)
def save_job_posting(
    title: str,
    company: str,
    content: str,
    analysis: str,
    url: str = "",
    match_score: float = 0.0
) -> dict:
    """
    Save an analyzed job posting to history.
    
    Args:
        title: Job title
        company: Company name
        content: Job posting content
        analysis: Analysis results
        url: Job posting URL
        match_score: Profile match score (0-100)
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    doc_id = store.save_job_posting(
        title=title,
        company=company,
        content=content,
        analysis=analysis,
        url=url,
        match_score=match_score
    )
    return {"success": True, "id": doc_id, "message": f"Saved job posting: {title} at {company}"}


@log_agent_call(history_logger)
def save_resume(
    target_role: str,
    resume_content: str,
    source_profile: str,
    target_company: str = "",
    optimization_score: float = 0.0,
    job_posting_id: str = ""
) -> dict:
    """
    Save a generated resume to history.
    
    Args:
        target_role: Role the resume targets
        resume_content: The resume content
        source_profile: Original profile used
        target_company: Target company (if specific)
        optimization_score: Optimization score (0-100)
        job_posting_id: Linked job posting ID
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    doc_id = store.save_resume(
        target_role=target_role,
        target_company=target_company or None,
        resume_content=resume_content,
        source_profile=source_profile,
        optimization_score=optimization_score,
        job_posting_id=job_posting_id or None
    )
    return {"success": True, "id": doc_id, "message": f"Saved resume for: {target_role}"}


@log_agent_call(history_logger)
def save_company_analysis(
    company_name: str,
    analysis: str,
    rating: float = 0.0,
    values: str = "[]"
) -> dict:
    """
    Save a company analysis to history.
    
    Args:
        company_name: Company name
        analysis: Analysis content
        rating: Overall rating (0-5)
        values: JSON string of company values list
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    try:
        values_list = json.loads(values) if values else []
    except json.JSONDecodeError:
        values_list = []
    
    doc_id = store.save_company_analysis(
        company_name=company_name,
        analysis=analysis,
        rating=rating,
        values=values_list
    )
    return {"success": True, "id": doc_id, "message": f"Saved company analysis: {company_name}"}


@log_agent_call(history_logger)
def save_search_session(
    search_criteria: str,
    results_summary: str,
    job_count: int,
    top_matches: str = "[]"
) -> dict:
    """
    Save a job search session to history.
    
    Args:
        search_criteria: JSON string of search criteria
        results_summary: Summary of results
        job_count: Number of jobs found
        top_matches: JSON string of top matching jobs
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    try:
        criteria_dict = json.loads(search_criteria) if search_criteria else {}
        matches_list = json.loads(top_matches) if top_matches else []
    except json.JSONDecodeError:
        criteria_dict = {"raw": search_criteria}
        matches_list = []
    
    doc_id = store.save_search_session(
        search_criteria=criteria_dict,
        results_summary=results_summary,
        job_count=job_count,
        top_matches=matches_list
    )
    return {"success": True, "id": doc_id, "message": f"Saved search session ({job_count} jobs)"}


@log_agent_call(history_logger)
def search_job_postings(
    query: str,
    n_results: int = 5,
    company_filter: str = ""
) -> dict:
    """
    Search similar job postings in history.
    
    Args:
        query: Search query
        n_results: Maximum results to return
        company_filter: Filter by company name
    
    Returns:
        List of matching job postings
    """
    store = get_vector_store()
    results = store.search_job_postings(
        query=query,
        n_results=n_results,
        company_filter=company_filter or None
    )
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def search_resumes(
    query: str,
    n_results: int = 5,
    role_filter: str = ""
) -> dict:
    """
    Search similar resumes in history.
    
    Args:
        query: Search query
        n_results: Maximum results to return
        role_filter: Filter by target role
    
    Returns:
        List of matching resumes
    """
    store = get_vector_store()
    results = store.search_resumes(
        query=query,
        n_results=n_results,
        role_filter=role_filter or None
    )
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def search_company_analyses(query: str, n_results: int = 5) -> dict:
    """
    Search company analyses in history.
    
    Args:
        query: Search query
        n_results: Maximum results to return
    
    Returns:
        List of matching company analyses
    """
    store = get_vector_store()
    results = store.search_company_analyses(query=query, n_results=n_results)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_company_analysis(company_name: str) -> dict:
    """
    Get existing analysis for a company.
    
    Args:
        company_name: Company name to look up
    
    Returns:
        Company analysis if found, or not_found message
    """
    store = get_vector_store()
    result = store.get_company_analysis(company_name)
    if result:
        return {"found": True, "analysis": result}
    return {"found": False, "message": f"No analysis found for {company_name}"}


@log_agent_call(history_logger)
def get_recent_job_postings(limit: int = 10) -> dict:
    """
    Get most recent job postings from history.
    
    Args:
        limit: Maximum number to return
    
    Returns:
        List of recent job postings
    """
    store = get_vector_store()
    results = store.get_recent_job_postings(limit=limit)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_history_stats() -> dict:
    """
    Get statistics about stored history.
    
    Returns:
        Stats including counts for each collection
    """
    store = get_vector_store()
    return store.get_stats()


# =============================================================================
# User Profile Tools (Profile Analyst Storage)
# =============================================================================

@log_agent_call(history_logger)
def save_user_profile(
    name: str,
    profile_content: str,
    skills: str = "[]",
    experience_years: int = 0,
    current_role: str = "",
    target_roles: str = "[]",
    education: str = "[]",
    certifications: str = "[]",
    achievements: str = "[]",
    values: str = "[]",
    work_preferences: str = "{}",
    is_primary: bool = False
) -> dict:
    """
    Save a user profile for job matching.
    
    Args:
        name: Profile name (e.g., "Full Profile", "Technical Summary")
        profile_content: Full profile text/content
        skills: JSON array of skills
        experience_years: Years of experience
        current_role: Current job role
        target_roles: JSON array of desired roles
        education: JSON array of education entries
        certifications: JSON array of certifications
        achievements: JSON array of key achievements
        values: JSON array of personal/professional values
        work_preferences: JSON object with remote, location, salary preferences
        is_primary: Set as primary profile
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    
    def parse_json(s, default):
        if not s or s in ("[]", "{}"):
            return default
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return default
    
    doc_id = store.save_user_profile(
        name=name,
        profile_content=profile_content,
        skills=parse_json(skills, []),
        experience_years=experience_years,
        current_role=current_role or None,
        target_roles=parse_json(target_roles, []),
        education=parse_json(education, []),
        certifications=parse_json(certifications, []),
        achievements=parse_json(achievements, []),
        values=parse_json(values, []),
        work_preferences=parse_json(work_preferences, {}),
        is_primary=is_primary
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved user profile: {name}" + (" (set as primary)" if is_primary else "")
    }


@log_agent_call(history_logger)
def get_primary_profile() -> dict:
    """
    Get the primary user profile.
    
    Returns:
        Primary profile if found
    """
    store = get_vector_store()
    result = store.get_primary_profile()
    
    if result:
        return {"found": True, "profile": result}
    return {"found": False, "message": "No primary profile set. Use save_user_profile with is_primary=True."}


@log_agent_call(history_logger)
def get_user_profile(profile_id: str) -> dict:
    """
    Get a specific user profile by ID.
    
    Args:
        profile_id: ID of the profile
    
    Returns:
        Profile if found
    """
    store = get_vector_store()
    result = store.get_user_profile(profile_id)
    
    if result:
        return {"found": True, "profile": result}
    return {"found": False, "message": f"Profile not found: {profile_id}"}


@log_agent_call(history_logger)
def list_user_profiles() -> dict:
    """
    List all saved user profiles.
    
    Returns:
        List of user profiles
    """
    store = get_vector_store()
    results = store.list_user_profiles()
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def update_user_profile(
    profile_id: str,
    name: str = "",
    profile_content: str = "",
    skills: str = "",
    experience_years: int = -1,
    current_role: str = "",
    target_roles: str = "",
    is_primary: bool = False
) -> dict:
    """
    Update an existing user profile.
    
    Args:
        profile_id: ID of profile to update (required)
        name: New name (optional)
        profile_content: New content (optional)
        skills: New skills JSON array (optional)
        experience_years: New years (-1 = no change)
        current_role: New current role (optional)
        target_roles: New target roles JSON array (optional)
        is_primary: Set as primary (optional)
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    
    updates = {}
    if name:
        updates["name"] = name
    if profile_content:
        updates["profile_content"] = profile_content
    if skills:
        try:
            updates["skills"] = json.loads(skills)
        except json.JSONDecodeError:
            updates["skills"] = [skills]
    if experience_years >= 0:
        updates["experience_years"] = experience_years
    if current_role:
        updates["current_role"] = current_role
    if target_roles:
        try:
            updates["target_roles"] = json.loads(target_roles)
        except json.JSONDecodeError:
            updates["target_roles"] = [target_roles]
    if is_primary:
        updates["is_primary"] = is_primary
    
    success = store.update_user_profile(profile_id, **updates)
    
    if success:
        return {"success": True, "message": f"Updated profile: {profile_id}"}
    return {"success": False, "message": f"Profile not found: {profile_id}"}


@log_agent_call(history_logger)
def delete_user_profile(profile_id: str) -> dict:
    """
    Delete a user profile.
    
    Args:
        profile_id: ID of profile to delete
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    success = store.delete_user_profile(profile_id)
    
    if success:
        return {"success": True, "message": f"Deleted profile: {profile_id}"}
    return {"success": False, "message": f"Profile not found: {profile_id}"}


@log_agent_call(history_logger)
def search_user_profiles(query: str, n_results: int = 5) -> dict:
    """
    Search user profiles.
    
    Args:
        query: Search query
        n_results: Maximum results
    
    Returns:
        Matching profiles
    """
    store = get_vector_store()
    results = store.search_user_profiles(query=query, n_results=n_results)
    return {"results": results, "count": len(results)}


# =============================================================================
# Resume Versions Tools (Application Designer Storage)
# =============================================================================

@log_agent_call(history_logger)
def save_resume_version(
    version_name: str,
    target_role: str,
    resume_content: str,
    version_descriptor: str,
    target_company: str = "",
    base_profile_id: str = "",
    job_posting_id: str = "",
    is_master: bool = False
) -> dict:
    """
    Save a resume version with descriptor.
    
    Args:
        version_name: Name for this version (e.g., "Technical Focus", "Leadership Focus")
        target_role: Target job role
        resume_content: The resume content
        version_descriptor: Description of what makes this version unique
        target_company: Target company (if specific)
        base_profile_id: ID of user profile this is based on
        job_posting_id: ID of job posting this was tailored for
        is_master: Whether this is the master/base resume
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    doc_id = store.save_resume_version(
        version_name=version_name,
        target_role=target_role,
        target_company=target_company or None,
        resume_content=resume_content,
        version_descriptor=version_descriptor,
        base_profile_id=base_profile_id or None,
        job_posting_id=job_posting_id or None,
        is_master=is_master
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved resume version: {version_name}" + (" (master)" if is_master else "")
    }


@log_agent_call(history_logger)
def get_master_resume() -> dict:
    """
    Get the master/base resume version.
    
    Returns:
        Master resume if found
    """
    store = get_vector_store()
    result = store.get_master_resume()
    
    if result:
        return {"found": True, "resume": result}
    return {"found": False, "message": "No master resume set. Use save_resume_version with is_master=True."}


@log_agent_call(history_logger)
def list_resume_versions() -> dict:
    """
    List all resume versions with their descriptors.
    
    Returns:
        List of resume versions
    """
    store = get_vector_store()
    results = store.list_resume_versions()
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_resume_versions(target_role: str = "", limit: int = 10) -> dict:
    """
    Get resume versions, optionally filtered by role.
    
    Args:
        target_role: Filter by target role (optional)
        limit: Maximum results
    
    Returns:
        List of resume versions
    """
    store = get_vector_store()
    results = store.get_resume_versions(
        target_role=target_role or None,
        limit=limit
    )
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def search_resume_versions(query: str, n_results: int = 5) -> dict:
    """
    Search resume versions by content/descriptor.
    
    Args:
        query: Search query
        n_results: Maximum results
    
    Returns:
        Matching resume versions
    """
    store = get_vector_store()
    results = store.search_resume_versions(query=query, n_results=n_results)
    return {"results": results, "count": len(results)}


# =============================================================================
# Cover Letter Tools (Application Designer Storage)
# =============================================================================

@log_agent_call(history_logger)
def save_cover_letter(
    target_role: str,
    target_company: str,
    cover_letter_content: str,
    job_posting_id: str = "",
    resume_version_id: str = "",
    key_highlights: str = "[]",
    tone: str = "professional"
) -> dict:
    """
    Save a cover letter.
    
    Args:
        target_role: Target job role
        target_company: Target company
        cover_letter_content: The cover letter content
        job_posting_id: ID of job posting this was written for
        resume_version_id: ID of resume version this accompanies
        key_highlights: JSON array of key achievements highlighted
        tone: Tone of the letter (formal/conversational/enthusiastic)
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    
    try:
        highlights_list = json.loads(key_highlights) if key_highlights and key_highlights != "[]" else []
    except json.JSONDecodeError:
        highlights_list = [key_highlights] if key_highlights else []
    
    doc_id = store.save_cover_letter(
        target_role=target_role,
        target_company=target_company,
        cover_letter_content=cover_letter_content,
        job_posting_id=job_posting_id or None,
        resume_version_id=resume_version_id or None,
        key_highlights=highlights_list,
        tone=tone
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved cover letter for: {target_role} at {target_company}"
    }


@log_agent_call(history_logger)
def get_cover_letters_for_company(company: str, limit: int = 5) -> dict:
    """
    Get cover letters for a specific company.
    
    Args:
        company: Company name
        limit: Maximum results
    
    Returns:
        Cover letters for the company
    """
    store = get_vector_store()
    results = store.get_cover_letters_for_company(company=company, limit=limit)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def search_cover_letters(query: str, n_results: int = 5) -> dict:
    """
    Search cover letters.
    
    Args:
        query: Search query
        n_results: Maximum results
    
    Returns:
        Matching cover letters
    """
    store = get_vector_store()
    results = store.search_cover_letters(query=query, n_results=n_results)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_recent_cover_letters(limit: int = 10) -> dict:
    """
    Get most recent cover letters.
    
    Args:
        limit: Maximum results
    
    Returns:
        Recent cover letters
    """
    store = get_vector_store()
    results = store.get_recent_cover_letters(limit=limit)
    return {"results": results, "count": len(results)}


# =============================================================================
# Resume Templates Tools (Application Designer Storage)
# =============================================================================

@log_agent_call(history_logger)
def save_resume_template(
    name: str,
    description: str,
    template_type: str,
    styles_json: str,
    sections_order: str,
    section_formatting: str = "{}",
    is_default: bool = False
) -> dict:
    """
    Save a resume template/formatting configuration.
    
    Args:
        name: Template name (e.g., "Professional", "Technical Focus")
        description: Description of when to use this template
        template_type: Type: "professional", "compact", "leadership", "technical", "custom"
        styles_json: JSON object with header_size, section_size, body_size, line_spacing, margins
        sections_order: JSON array of section names in order (e.g., '["Summary", "Experience", "Skills"]')
        section_formatting: JSON object with per-section formatting rules (optional)
        is_default: Set as default template
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    
    try:
        styles = json.loads(styles_json) if styles_json else {}
    except json.JSONDecodeError:
        return {"success": False, "error": "Invalid styles_json format"}
    
    try:
        sections = json.loads(sections_order) if sections_order else []
    except json.JSONDecodeError:
        sections = [sections_order] if sections_order else []
    
    try:
        formatting = json.loads(section_formatting) if section_formatting and section_formatting != "{}" else {}
    except json.JSONDecodeError:
        formatting = {}
    
    doc_id = store.save_resume_template(
        name=name,
        description=description,
        template_type=template_type,
        styles=styles,
        sections_order=sections,
        section_formatting=formatting,
        is_default=is_default
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved resume template: {name}" + (" (set as default)" if is_default else "")
    }


@log_agent_call(history_logger)
def get_resume_template(template_id: str) -> dict:
    """
    Get a specific resume template by ID.
    
    Args:
        template_id: ID of the template
    
    Returns:
        Template if found
    """
    store = get_vector_store()
    result = store.get_resume_template(template_id)
    
    if result:
        return {"found": True, "template": result}
    return {"found": False, "message": f"Template not found: {template_id}"}


@log_agent_call(history_logger)
def get_default_resume_template() -> dict:
    """
    Get the default resume template.
    
    Returns:
        Default template if set
    """
    store = get_vector_store()
    result = store.get_default_resume_template()
    
    if result:
        return {"found": True, "template": result}
    return {"found": False, "message": "No default template set. Use save_resume_template with is_default=True."}


@log_agent_call(history_logger)
def list_resume_templates() -> dict:
    """
    List all resume templates.
    
    Returns:
        List of templates
    """
    store = get_vector_store()
    results = store.list_resume_templates()
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def delete_resume_template(template_id: str) -> dict:
    """
    Delete a resume template.
    
    Args:
        template_id: ID of template to delete
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    success = store.delete_resume_template(template_id)
    
    if success:
        return {"success": True, "message": f"Deleted template: {template_id}"}
    return {"success": False, "message": f"Template not found: {template_id}"}


# =============================================================================
# Design Instructions Tools (Guard Rails & Requirements)
# =============================================================================

@log_agent_call(history_logger)
def save_design_instruction(
    name: str,
    instruction_type: str,
    instruction_text: str,
    applies_to: str,
    priority: str = "medium",
    is_active: bool = True,
    source_verification_required: bool = False
) -> dict:
    """
    Save a design instruction or guard rail.
    
    Args:
        name: Instruction name (e.g., "No Fabricated Experience")
        instruction_type: "guard_rail", "requirement", "formatting", or "content"
        instruction_text: The actual instruction/rule text
        applies_to: JSON array of what this applies to: '["resume"]', '["cover_letter"]', '["both"]'
        priority: "critical", "high", "medium", or "low"
        is_active: Whether currently active
        source_verification_required: If claims must be traced to source profile
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    
    try:
        applies_list = json.loads(applies_to) if applies_to else ["both"]
    except json.JSONDecodeError:
        applies_list = [applies_to] if applies_to else ["both"]
    
    doc_id = store.save_design_instruction(
        name=name,
        instruction_type=instruction_type,
        instruction_text=instruction_text,
        applies_to=applies_list,
        priority=priority,
        is_active=is_active,
        source_verification_required=source_verification_required
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved design instruction: {name} ({instruction_type})"
    }


@log_agent_call(history_logger)
def get_active_instructions(
    applies_to: str = "",
    instruction_type: str = ""
) -> dict:
    """
    Get all active design instructions, optionally filtered.
    
    Args:
        applies_to: Filter by "resume", "cover_letter", or "" for all
        instruction_type: Filter by type or "" for all
    
    Returns:
        List of active instructions
    """
    store = get_vector_store()
    results = store.get_active_instructions(
        applies_to=applies_to or None,
        instruction_type=instruction_type or None
    )
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_guard_rails(applies_to: str = "") -> dict:
    """
    Get all active guard rail instructions.
    
    Args:
        applies_to: Filter by "resume", "cover_letter", or "" for all
    
    Returns:
        List of guard rails
    """
    store = get_vector_store()
    results = store.get_guard_rails(applies_to=applies_to or None)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def get_requirements(applies_to: str = "") -> dict:
    """
    Get all active requirement instructions.
    
    Args:
        applies_to: Filter by "resume", "cover_letter", or "" for all
    
    Returns:
        List of requirements
    """
    store = get_vector_store()
    results = store.get_requirements(applies_to=applies_to or None)
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def list_design_instructions() -> dict:
    """
    List all design instructions.
    
    Returns:
        List of all instructions
    """
    store = get_vector_store()
    results = store.list_design_instructions()
    return {"results": results, "count": len(results)}


@log_agent_call(history_logger)
def toggle_instruction(instruction_id: str, is_active: bool) -> dict:
    """
    Enable or disable a design instruction.
    
    Args:
        instruction_id: ID of instruction
        is_active: True to enable, False to disable
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    success = store.toggle_instruction(instruction_id, is_active)
    
    status = "enabled" if is_active else "disabled"
    if success:
        return {"success": True, "message": f"Instruction {status}: {instruction_id}"}
    return {"success": False, "message": f"Instruction not found: {instruction_id}"}


@log_agent_call(history_logger)
def delete_design_instruction(instruction_id: str) -> dict:
    """
    Delete a design instruction.
    
    Args:
        instruction_id: ID of instruction to delete
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    success = store.delete_design_instruction(instruction_id)
    
    if success:
        return {"success": True, "message": f"Deleted instruction: {instruction_id}"}
    return {"success": False, "message": f"Instruction not found: {instruction_id}"}


# =============================================================================
# Search Criteria Tools
# =============================================================================

@log_agent_call(history_logger)
def save_search_criteria(
    name: str,
    role: str = "",
    location: str = "",
    keywords: str = "[]",
    salary_min: int = 0,
    salary_max: int = 0,
    remote_preference: str = "any",
    experience_level: str = "",
    company_size: str = "",
    industries: str = "[]",
    exclude_companies: str = "[]",
    is_default: bool = False
) -> dict:
    """
    Save job search criteria for reuse.
    
    Args:
        name: Friendly name for this saved search (e.g., "Remote ML Jobs SF")
        role: Target job role/title (e.g., "Software Engineer")
        location: Preferred location (e.g., "San Francisco, CA" or "Remote")
        keywords: JSON array of required keywords/skills (e.g., '["Python", "AWS"]')
        salary_min: Minimum salary (0 for no minimum)
        salary_max: Maximum salary (0 for no maximum)
        remote_preference: "remote", "hybrid", "onsite", or "any"
        experience_level: "entry", "mid", "senior", or "executive"
        company_size: "startup", "small", "medium", "large", or "enterprise"
        industries: JSON array of target industries (e.g., '["Tech", "Finance"]')
        exclude_companies: JSON array of companies to exclude
        is_default: Set as the default search criteria
    
    Returns:
        Result with saved ID
    """
    store = get_vector_store()
    
    try:
        keywords_list = json.loads(keywords) if keywords and keywords != "[]" else []
    except json.JSONDecodeError:
        keywords_list = [keywords] if keywords else []
    
    try:
        industries_list = json.loads(industries) if industries and industries != "[]" else []
    except json.JSONDecodeError:
        industries_list = [industries] if industries else []
    
    try:
        exclude_list = json.loads(exclude_companies) if exclude_companies and exclude_companies != "[]" else []
    except json.JSONDecodeError:
        exclude_list = [exclude_companies] if exclude_companies else []
    
    doc_id = store.save_search_criteria(
        name=name,
        role=role or None,
        location=location or None,
        keywords=keywords_list or None,
        salary_min=salary_min or None,
        salary_max=salary_max or None,
        remote_preference=remote_preference or None,
        experience_level=experience_level or None,
        company_size=company_size or None,
        industries=industries_list or None,
        exclude_companies=exclude_list or None,
        is_default=is_default
    )
    
    return {
        "success": True,
        "id": doc_id,
        "message": f"Saved search criteria: {name}" + (" (set as default)" if is_default else "")
    }


@log_agent_call(history_logger)
def get_search_criteria(criteria_id: str = "", name: str = "") -> dict:
    """
    Get saved search criteria by ID or name.
    
    Args:
        criteria_id: ID of the saved criteria
        name: Name of the saved criteria (alternative to ID)
    
    Returns:
        Search criteria if found
    """
    store = get_vector_store()
    
    if criteria_id:
        result = store.get_search_criteria(criteria_id)
    elif name:
        result = store.get_search_criteria_by_name(name)
    else:
        return {"found": False, "message": "Please provide either criteria_id or name"}
    
    if result:
        return {"found": True, "criteria": result}
    return {"found": False, "message": f"Search criteria not found"}


@log_agent_call(history_logger)
def get_default_search_criteria() -> dict:
    """
    Get the default search criteria if one is set.
    
    Returns:
        Default search criteria or message if not set
    """
    store = get_vector_store()
    result = store.get_default_search_criteria()
    
    if result:
        return {"found": True, "criteria": result}
    return {"found": False, "message": "No default search criteria set"}


@log_agent_call(history_logger)
def list_search_criteria(limit: int = 20) -> dict:
    """
    List all saved search criteria.
    
    Args:
        limit: Maximum number to return
    
    Returns:
        List of saved search criteria
    """
    store = get_vector_store()
    results = store.list_search_criteria(limit=limit)
    
    # Simplify output for display
    simplified = []
    for item in results:
        criteria = item.get("criteria", {})
        metadata = item.get("metadata", {})
        simplified.append({
            "id": item.get("id"),
            "name": metadata.get("name"),
            "role": criteria.get("role"),
            "location": criteria.get("location"),
            "remote": criteria.get("remote_preference"),
            "is_default": metadata.get("is_default", False),
            "use_count": metadata.get("use_count", 0),
            "last_used": metadata.get("last_used")
        })
    
    return {"results": simplified, "count": len(simplified)}


@log_agent_call(history_logger)
def update_search_criteria(
    criteria_id: str,
    name: str = "",
    role: str = "",
    location: str = "",
    keywords: str = "",
    salary_min: int = -1,
    salary_max: int = -1,
    remote_preference: str = "",
    experience_level: str = "",
    is_default: bool = False
) -> dict:
    """
    Update existing search criteria.
    
    Args:
        criteria_id: ID of criteria to update (required)
        name: New name (optional, empty string = no change)
        role: New role (optional)
        location: New location (optional)
        keywords: New keywords JSON array (optional)
        salary_min: New minimum salary (-1 = no change)
        salary_max: New maximum salary (-1 = no change)
        remote_preference: New remote preference (optional)
        experience_level: New experience level (optional)
        is_default: Set as default (optional)
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    
    # Parse keywords if provided
    keywords_list = None
    if keywords:
        try:
            keywords_list = json.loads(keywords)
        except json.JSONDecodeError:
            keywords_list = [keywords]
    
    success = store.update_search_criteria(
        criteria_id=criteria_id,
        name=name or None,
        role=role or None,
        location=location or None,
        keywords=keywords_list,
        salary_min=salary_min if salary_min >= 0 else None,
        salary_max=salary_max if salary_max >= 0 else None,
        remote_preference=remote_preference or None,
        experience_level=experience_level or None,
        is_default=is_default if is_default else None
    )
    
    if success:
        return {"success": True, "message": f"Updated search criteria: {criteria_id}"}
    return {"success": False, "message": f"Search criteria not found: {criteria_id}"}


@log_agent_call(history_logger)
def delete_search_criteria(criteria_id: str) -> dict:
    """
    Delete saved search criteria.
    
    Args:
        criteria_id: ID of criteria to delete
    
    Returns:
        Success or failure message
    """
    store = get_vector_store()
    success = store.delete_search_criteria(criteria_id)
    
    if success:
        return {"success": True, "message": f"Deleted search criteria: {criteria_id}"}
    return {"success": False, "message": f"Search criteria not found: {criteria_id}"}


@log_agent_call(history_logger)
def use_search_criteria(criteria_id: str) -> dict:
    """
    Mark search criteria as used and return it for use.
    
    Args:
        criteria_id: ID of criteria to use
    
    Returns:
        The search criteria ready for use
    """
    store = get_vector_store()
    
    # Get the criteria
    result = store.get_search_criteria(criteria_id)
    if not result:
        return {"success": False, "message": f"Search criteria not found: {criteria_id}"}
    
    # Mark as used
    store.mark_criteria_used(criteria_id)
    
    return {
        "success": True,
        "criteria": result.get("criteria", {}),
        "name": result.get("metadata", {}).get("name"),
        "message": "Search criteria loaded. Use these filters for your job search."
    }


# =============================================================================
# Caching Tools - Response and Search Results Cache
# =============================================================================

@log_agent_call(history_logger)
def get_cached_response(
    cache_type: str,
    query: str,
    role: str = "",
    location: str = "",
    company: str = ""
) -> dict:
    """
    Get a cached agent response if available and not expired.
    
    Args:
        cache_type: Type of cache (search_results, job_analysis, company_analysis, market_analysis)
        query: The original query/input
        role: Job role (for search results)
        location: Location (for search results)
        company: Company name (for company analysis)
    
    Returns:
        Cached response or {"cached": False} if not found/expired
    """
    store = get_vector_store()
    result = store.get_cached_response(
        cache_type=cache_type,
        query=query,
        role=role,
        location=location,
        company=company
    )
    if result:
        return result
    return {"cached": False, "message": f"No valid cache found for {cache_type}"}


@log_agent_call(history_logger)
def set_cached_response(
    cache_type: str,
    query: str,
    response: str,
    sources: str = "[]",
    role: str = "",
    location: str = "",
    company: str = ""
) -> dict:
    """
    Cache an agent response for future reuse.
    
    Args:
        cache_type: Type of cache (search_results, job_analysis, company_analysis, market_analysis)
        query: The original query/input
        response: The response to cache
        sources: JSON string of source dicts with url, title, platform fields
        role: Job role (for search results)
        location: Location (for search results)
        company: Company name (for company analysis)
    
    Returns:
        Result with cache key
    """
    store = get_vector_store()
    try:
        sources_list = json.loads(sources) if sources else []
    except:
        sources_list = []
    
    cache_key = store.set_cached_response(
        cache_type=cache_type,
        query=query,
        response=response,
        sources=sources_list,
        role=role,
        location=location,
        company=company
    )
    return {
        "success": True,
        "cache_key": cache_key,
        "message": f"Cached {cache_type} response"
    }


@log_agent_call(history_logger)
def invalidate_cache(
    cache_type: str = "",
    older_than_hours: int = 0
) -> dict:
    """
    Invalidate cached responses.
    
    Args:
        cache_type: Type to invalidate (empty = all types)
        older_than_hours: Only invalidate entries older than this (0 = all)
    
    Returns:
        Result with count of invalidated entries
    """
    store = get_vector_store()
    count = store.invalidate_cache(
        cache_type=cache_type if cache_type else None,
        older_than_hours=older_than_hours if older_than_hours > 0 else None
    )
    return {
        "success": True,
        "invalidated_count": count,
        "message": f"Invalidated {count} cache entries"
    }


@log_agent_call(history_logger)
def get_cache_stats() -> dict:
    """
    Get statistics about the response cache.
    
    Returns:
        Cache statistics including counts by type
    """
    store = get_vector_store()
    return store.get_cache_stats()


@log_agent_call(history_logger)
def save_search_results(
    query: str,
    role: str,
    location: str,
    results: str,
    platform: str = ""
) -> dict:
    """
    Save search results with source links for caching.
    
    Args:
        query: The search query
        role: Job role searched
        location: Location searched
        results: JSON string of job results (each with title, company, url, platform)
        platform: Platform name if all from same source
    
    Returns:
        Result with cache key
    """
    store = get_vector_store()
    try:
        results_list = json.loads(results) if results else []
    except:
        results_list = []
    
    cache_key = store.save_search_results(
        query=query,
        role=role,
        location=location,
        results=results_list,
        platform=platform if platform else None
    )
    return {
        "success": True,
        "cache_key": cache_key,
        "results_count": len(results_list),
        "message": f"Cached {len(results_list)} search results"
    }


@log_agent_call(history_logger)
def get_cached_search_results(
    role: str,
    location: str,
    platform: str = "",
    max_age_hours: int = 24
) -> dict:
    """
    Get cached search results if available and fresh.
    
    Args:
        role: Job role to search
        location: Location to search
        platform: Specific platform or empty for all
        max_age_hours: Maximum age of cached results (default 24)
    
    Returns:
        Cached search results with source URLs or {"cached": False}
    """
    store = get_vector_store()
    result = store.get_cached_search_results(
        role=role,
        location=location,
        platform=platform if platform else None,
        max_age_hours=max_age_hours
    )
    if result:
        return result
    return {
        "cached": False,
        "message": f"No cached search results for {role} in {location}"
    }


# =============================================================================
# History Manager Agent
# =============================================================================

history_manager_agent = Agent(
    model=MODEL,
    name="history_manager_agent",
    description=(
        "Manages job search history using a vector database. Stores and retrieves "
        "job postings, resumes, resume versions, cover letters, user profiles, "
        "company analyses, search sessions, saved search criteria, resume templates, "
        "and design instructions/guard rails. "
        "Enables semantic search across history and tracks career search patterns."
    ),
    instruction=HISTORY_MANAGER_PROMPT,
    output_key="history_manager_output",
    tools=[
        # Job postings
        FunctionTool(func=save_job_posting),
        FunctionTool(func=search_job_postings),
        FunctionTool(func=get_recent_job_postings),
        # Resumes (general)
        FunctionTool(func=save_resume),
        FunctionTool(func=search_resumes),
        # User Profiles (Profile Analyst Storage)
        FunctionTool(func=save_user_profile),
        FunctionTool(func=get_primary_profile),
        FunctionTool(func=get_user_profile),
        FunctionTool(func=list_user_profiles),
        FunctionTool(func=update_user_profile),
        FunctionTool(func=delete_user_profile),
        FunctionTool(func=search_user_profiles),
        # Resume Versions (Application Designer Storage)
        FunctionTool(func=save_resume_version),
        FunctionTool(func=get_master_resume),
        FunctionTool(func=list_resume_versions),
        FunctionTool(func=get_resume_versions),
        FunctionTool(func=search_resume_versions),
        # Cover Letters (Application Designer Storage)
        FunctionTool(func=save_cover_letter),
        FunctionTool(func=get_cover_letters_for_company),
        FunctionTool(func=search_cover_letters),
        FunctionTool(func=get_recent_cover_letters),
        # Resume Templates (Application Designer Storage)
        FunctionTool(func=save_resume_template),
        FunctionTool(func=get_resume_template),
        FunctionTool(func=get_default_resume_template),
        FunctionTool(func=list_resume_templates),
        FunctionTool(func=delete_resume_template),
        # Design Instructions / Guard Rails
        FunctionTool(func=save_design_instruction),
        FunctionTool(func=get_active_instructions),
        FunctionTool(func=get_guard_rails),
        FunctionTool(func=get_requirements),
        FunctionTool(func=list_design_instructions),
        FunctionTool(func=toggle_instruction),
        FunctionTool(func=delete_design_instruction),
        # Company analyses
        FunctionTool(func=save_company_analysis),
        FunctionTool(func=search_company_analyses),
        FunctionTool(func=get_company_analysis),
        # Search sessions
        FunctionTool(func=save_search_session),
        # Search criteria (saved searches)
        FunctionTool(func=save_search_criteria),
        FunctionTool(func=get_search_criteria),
        FunctionTool(func=get_default_search_criteria),
        FunctionTool(func=list_search_criteria),
        FunctionTool(func=update_search_criteria),
        FunctionTool(func=delete_search_criteria),
        FunctionTool(func=use_search_criteria),
        # Stats
        FunctionTool(func=get_history_stats),
        # Caching (response cache and search results cache)
        FunctionTool(func=get_cached_response),
        FunctionTool(func=set_cached_response),
        FunctionTool(func=invalidate_cache),
        FunctionTool(func=get_cache_stats),
        FunctionTool(func=save_search_results),
        FunctionTool(func=get_cached_search_results),
    ],
)

