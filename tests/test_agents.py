"""Tests for job search agents."""

import pytest


class TestAgentImports:
    """Test that all agents can be imported successfully."""

    def test_import_root_agent(self) -> None:
        """Test that root_agent can be imported."""
        from job_agent_coordinator.agent import root_agent
        assert root_agent is not None

    def test_import_coordinator(self) -> None:
        """Test that coordinator can be imported."""
        from job_agent_coordinator.agent import job_agent_coordinator
        assert job_agent_coordinator is not None

    def test_import_profile_analyst(self) -> None:
        """Test that profile_analyst_agent can be imported."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        assert profile_analyst_agent is not None

    def test_import_resume_designer(self) -> None:
        """Test that resume_designer_agent can be imported."""
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        assert resume_designer_agent is not None

    def test_import_job_searcher(self) -> None:
        """Test that job_searcher_agent can be imported."""
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        assert job_searcher_agent is not None

    def test_import_job_posting_analyst(self) -> None:
        """Test that job_posting_analyst_agent can be imported."""
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        assert job_posting_analyst_agent is not None

    def test_import_market_analyst(self) -> None:
        """Test that market_analyst_agent can be imported."""
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent
        assert market_analyst_agent is not None

    def test_import_company_researcher(self) -> None:
        """Test that company_researcher_agent can be imported."""
        from job_agent_coordinator.sub_agents.company_researcher import company_researcher_agent
        assert company_researcher_agent is not None

    def test_import_history_manager(self) -> None:
        """Test that history_manager_agent can be imported."""
        from job_agent_coordinator.sub_agents.history_manager import history_manager_agent
        assert history_manager_agent is not None

    def test_import_parallel_agents(self) -> None:
        """Test that parallel agents can be imported."""
        from job_agent_coordinator.agent import (
            parallel_platform_search,
            enhanced_job_search_workflow,
            linkedin_search_agent,
            indeed_search_agent,
            glassdoor_search_agent,
        )
        assert parallel_platform_search is not None
        assert enhanced_job_search_workflow is not None
        assert linkedin_search_agent is not None
        assert indeed_search_agent is not None
        assert glassdoor_search_agent is not None

    def test_import_application_designer(self) -> None:
        """Test that application_designer_agent can be imported."""
        from job_agent_coordinator.sub_agents.application_designer import application_designer_agent
        assert application_designer_agent is not None


class TestAgentConfiguration:
    """Tests for agent configuration and structure."""

    def test_coordinator_name(self) -> None:
        """Test coordinator agent name."""
        from job_agent_coordinator.agent import job_agent_coordinator
        assert job_agent_coordinator.name == "job_agent_coordinator"

    def test_coordinator_model(self) -> None:
        """Test coordinator uses correct model."""
        from job_agent_coordinator.agent import job_agent_coordinator
        assert job_agent_coordinator.model == "gemini-2.5-pro"

    def test_profile_analyst_config(self) -> None:
        """Test profile analyst agent configuration."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        assert profile_analyst_agent.name == "profile_analyst_agent"
        assert profile_analyst_agent.output_key == "profile_analysis_output"
        assert profile_analyst_agent.model == "gemini-2.5-pro"

    def test_resume_designer_config(self) -> None:
        """Test resume designer agent configuration."""
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        assert resume_designer_agent.name == "resume_designer_agent"
        assert resume_designer_agent.output_key == "resume_design_output"
        assert resume_designer_agent.model == "gemini-2.5-pro"

    def test_job_searcher_config(self) -> None:
        """Test job searcher agent configuration."""
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        assert job_searcher_agent.name == "job_searcher_agent"
        assert job_searcher_agent.output_key == "job_search_output"
        assert job_searcher_agent.model == "gemini-2.5-pro"

    def test_job_posting_analyst_config(self) -> None:
        """Test job posting analyst agent configuration."""
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        assert job_posting_analyst_agent.name == "job_posting_analyst_agent"
        assert job_posting_analyst_agent.output_key == "job_posting_analysis_output"
        assert job_posting_analyst_agent.model == "gemini-2.5-pro"

    def test_market_analyst_config(self) -> None:
        """Test market analyst agent configuration."""
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent
        assert market_analyst_agent.name == "market_analyst_agent"
        assert market_analyst_agent.output_key == "market_analysis_output"
        assert market_analyst_agent.model == "gemini-2.5-pro"

    def test_company_researcher_config(self) -> None:
        """Test company researcher agent configuration."""
        from job_agent_coordinator.sub_agents.company_researcher import company_researcher_agent
        assert company_researcher_agent.name == "company_researcher_agent"
        assert company_researcher_agent.output_key == "company_research_results"
        assert company_researcher_agent.model == "gemini-2.5-flash"

    def test_history_manager_config(self) -> None:
        """Test history manager agent configuration."""
        from job_agent_coordinator.sub_agents.history_manager import history_manager_agent
        assert history_manager_agent.name == "history_manager_agent"
        assert history_manager_agent.output_key == "history_manager_output"
        assert history_manager_agent.model == "gemini-2.5-flash"

    def test_parallel_platform_search_config(self) -> None:
        """Test parallel platform search agent configuration."""
        from job_agent_coordinator.agent import parallel_platform_search
        assert parallel_platform_search.name == "parallel_platform_search"
        # Always 3 sub-agents: linkedin, indeed, glassdoor (using google_search)
        assert len(parallel_platform_search.sub_agents) == 3
        agent_names = [a.name for a in parallel_platform_search.sub_agents]
        assert "linkedin_search_agent" in agent_names
        assert "indeed_search_agent" in agent_names
        assert "glassdoor_search_agent" in agent_names

    def test_coordinator_has_tools(self) -> None:
        """Test that coordinator has expected tool count."""
        from job_agent_coordinator.agent import job_agent_coordinator
        assert job_agent_coordinator.tools is not None
        # 7 sub-agents + 1 enhanced_job_search_workflow = 8 tools
        assert len(job_agent_coordinator.tools) == 8


class TestAgentDescriptions:
    """Tests for agent descriptions."""

    def test_coordinator_description(self) -> None:
        """Test coordinator has meaningful description."""
        from job_agent_coordinator.agent import job_agent_coordinator
        assert "job search" in job_agent_coordinator.description.lower()
        assert "orchestrat" in job_agent_coordinator.description.lower()

    def test_profile_analyst_description(self) -> None:
        """Test profile analyst has meaningful description."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        assert "profile" in profile_analyst_agent.description.lower()
        assert "skill" in profile_analyst_agent.description.lower()

    def test_resume_designer_description(self) -> None:
        """Test resume designer has meaningful description."""
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        assert "resume" in resume_designer_agent.description.lower()

    def test_job_searcher_description(self) -> None:
        """Test job searcher has meaningful description."""
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        assert "job" in job_searcher_agent.description.lower()
        assert "search" in job_searcher_agent.description.lower()

    def test_job_posting_analyst_description(self) -> None:
        """Test job posting analyst has meaningful description."""
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        assert "job" in job_posting_analyst_agent.description.lower()
        assert "posting" in job_posting_analyst_agent.description.lower()

    def test_market_analyst_description(self) -> None:
        """Test market analyst has meaningful description."""
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent
        assert "market" in market_analyst_agent.description.lower()
        assert "intelligence" in market_analyst_agent.description.lower()

    def test_company_researcher_description(self) -> None:
        """Test company researcher has meaningful description."""
        from job_agent_coordinator.sub_agents.company_researcher import company_researcher_agent
        assert "compan" in company_researcher_agent.description.lower()
        assert "research" in company_researcher_agent.description.lower()

    def test_history_manager_description(self) -> None:
        """Test history manager has meaningful description."""
        from job_agent_coordinator.sub_agents.history_manager import history_manager_agent
        assert "history" in history_manager_agent.description.lower()
        assert "vector" in history_manager_agent.description.lower()


class TestAgentTools:
    """Tests for agent tools configuration."""

    def test_profile_analyst_has_google_search(self) -> None:
        """Test profile analyst has google_search tool."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        assert profile_analyst_agent.tools is not None
        assert len(profile_analyst_agent.tools) > 0

    def test_resume_designer_has_google_search(self) -> None:
        """Test resume designer has google_search tool."""
        from job_agent_coordinator.sub_agents.resume_designer import resume_designer_agent
        assert resume_designer_agent.tools is not None
        assert len(resume_designer_agent.tools) > 0

    def test_job_searcher_has_google_search(self) -> None:
        """Test job searcher has google_search tool."""
        from job_agent_coordinator.sub_agents.job_searcher import job_searcher_agent
        assert job_searcher_agent.tools is not None
        assert len(job_searcher_agent.tools) > 0

    def test_job_posting_analyst_has_google_search(self) -> None:
        """Test job posting analyst has google_search tool."""
        from job_agent_coordinator.sub_agents.job_posting_analyst import job_posting_analyst_agent
        assert job_posting_analyst_agent.tools is not None
        assert len(job_posting_analyst_agent.tools) > 0

    def test_market_analyst_has_google_search(self) -> None:
        """Test market analyst has google_search tool."""
        from job_agent_coordinator.sub_agents.market_analyst import market_analyst_agent
        assert market_analyst_agent.tools is not None
        assert len(market_analyst_agent.tools) > 0

    def test_company_researcher_has_google_search(self) -> None:
        """Test company researcher has google_search tool."""
        from job_agent_coordinator.sub_agents.company_researcher import company_researcher_agent
        assert company_researcher_agent.tools is not None
        assert len(company_researcher_agent.tools) > 0

    def test_history_manager_has_function_tools(self) -> None:
        """Test history manager has function tools."""
        from job_agent_coordinator.sub_agents.history_manager import history_manager_agent
        assert history_manager_agent.tools is not None
        # History manager has many tools for managing different collections:
        # Job postings (3) + Resumes (2) + User profiles (7) + Resume versions (5) + 
        # Cover letters (4) + Company (3) + Search sessions (1) + Search criteria (7) + Stats (1) = 33
        assert len(history_manager_agent.tools) >= 30


class TestPrompts:
    """Tests for agent prompts."""

    def test_coordinator_prompt_exists(self) -> None:
        """Test coordinator prompt is defined."""
        from job_agent_coordinator.prompt import JOB_AGENT_COORDINATOR_PROMPT
        assert JOB_AGENT_COORDINATOR_PROMPT is not None
        assert len(JOB_AGENT_COORDINATOR_PROMPT) > 100

    def test_profile_analyst_prompt_exists(self) -> None:
        """Test profile analyst prompt is defined."""
        from job_agent_coordinator.sub_agents.profile_analyst.prompt import PROFILE_ANALYST_PROMPT
        assert PROFILE_ANALYST_PROMPT is not None
        assert len(PROFILE_ANALYST_PROMPT) > 100

    def test_resume_designer_prompt_exists(self) -> None:
        """Test resume designer prompt is defined."""
        from job_agent_coordinator.sub_agents.resume_designer.prompt import RESUME_DESIGNER_PROMPT
        assert RESUME_DESIGNER_PROMPT is not None
        assert len(RESUME_DESIGNER_PROMPT) > 100

    def test_resume_designer_has_guard_rails(self) -> None:
        """Test resume designer prompt includes truthfulness guard rails."""
        from job_agent_coordinator.sub_agents.resume_designer.prompt import RESUME_DESIGNER_PROMPT
        assert "guard_rails" in RESUME_DESIGNER_PROMPT.lower()
        assert "truthfulness" in RESUME_DESIGNER_PROMPT.lower()
        assert "never fabricate" in RESUME_DESIGNER_PROMPT.lower()

    def test_job_searcher_prompt_exists(self) -> None:
        """Test job searcher prompt is defined."""
        from job_agent_coordinator.sub_agents.job_searcher.prompt import JOB_SEARCHER_PROMPT
        assert JOB_SEARCHER_PROMPT is not None
        assert len(JOB_SEARCHER_PROMPT) > 100

    def test_job_posting_analyst_prompt_exists(self) -> None:
        """Test job posting analyst prompt is defined."""
        from job_agent_coordinator.sub_agents.job_posting_analyst.prompt import JOB_POSTING_ANALYST_PROMPT
        assert JOB_POSTING_ANALYST_PROMPT is not None
        assert len(JOB_POSTING_ANALYST_PROMPT) > 100

    def test_market_analyst_prompt_exists(self) -> None:
        """Test market analyst prompt is defined."""
        from job_agent_coordinator.sub_agents.market_analyst.prompt import MARKET_ANALYST_PROMPT
        assert MARKET_ANALYST_PROMPT is not None
        assert len(MARKET_ANALYST_PROMPT) > 100

    def test_company_researcher_prompt_exists(self) -> None:
        """Test company researcher prompt is defined."""
        from job_agent_coordinator.sub_agents.company_researcher.prompt import COMPANY_RESEARCHER_PROMPT
        assert COMPANY_RESEARCHER_PROMPT is not None
        assert len(COMPANY_RESEARCHER_PROMPT) > 100

    def test_history_manager_prompt_exists(self) -> None:
        """Test history manager prompt is defined."""
        from job_agent_coordinator.sub_agents.history_manager.prompt import HISTORY_MANAGER_PROMPT
        assert HISTORY_MANAGER_PROMPT is not None
        assert len(HISTORY_MANAGER_PROMPT) > 100


class TestParallelSearchAgents:
    """Tests for parallel search agent configurations."""

    def test_linkedin_search_agent(self) -> None:
        """Test LinkedIn search agent configuration."""
        from job_agent_coordinator.agent import linkedin_search_agent
        assert linkedin_search_agent.name == "linkedin_search_agent"
        assert linkedin_search_agent.output_key == "linkedin_search_results"
        assert linkedin_search_agent.model == "gemini-2.5-flash"

    def test_indeed_search_agent(self) -> None:
        """Test Indeed search agent configuration."""
        from job_agent_coordinator.agent import indeed_search_agent
        assert indeed_search_agent.name == "indeed_search_agent"
        assert indeed_search_agent.output_key == "indeed_search_results"
        assert indeed_search_agent.model == "gemini-2.5-flash"

    def test_glassdoor_search_agent(self) -> None:
        """Test Glassdoor search agent configuration."""
        from job_agent_coordinator.agent import glassdoor_search_agent
        assert glassdoor_search_agent.name == "glassdoor_search_agent"
        assert glassdoor_search_agent.output_key == "glassdoor_search_results"
        assert glassdoor_search_agent.model == "gemini-2.5-flash"

    def test_search_results_aggregator(self) -> None:
        """Test search results aggregator agent configuration."""
        from job_agent_coordinator.agent import search_results_aggregator
        assert search_results_aggregator.name == "search_results_aggregator"
        assert search_results_aggregator.output_key == "aggregated_search_results"

    def test_enhanced_job_search_workflow_structure(self) -> None:
        """Test enhanced job search workflow has correct structure."""
        from job_agent_coordinator.agent import enhanced_job_search_workflow
        assert enhanced_job_search_workflow.name == "enhanced_job_search_workflow"
        # 4 stages: parallel_platform_search, aggregator, parallel_job_analysis, synthesizer
        assert len(enhanced_job_search_workflow.sub_agents) == 4


class TestRootAgent:
    """Tests for root agent configuration."""

    def test_root_agent_is_coordinator(self) -> None:
        """Test root_agent is the job_agent_coordinator."""
        from job_agent_coordinator.agent import root_agent, job_agent_coordinator
        assert root_agent is job_agent_coordinator

    def test_root_agent_via_package_import(self) -> None:
        """Test root_agent is accessible via package import."""
        # This tests the __init__.py setup
        import job_agent_coordinator
        assert hasattr(job_agent_coordinator, 'agent')


class TestHistoryManager:
    """Tests for history manager and vector store."""

    def test_vector_store_import(self) -> None:
        """Test vector store can be imported."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import (
            JobSearchVectorStore,
            get_vector_store,
        )
        assert JobSearchVectorStore is not None
        assert get_vector_store is not None

    def test_vector_store_initialization(self) -> None:
        """Test vector store can be initialized."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import (
            JobSearchVectorStore,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobSearchVectorStore(persist_directory=tmpdir)
            stats = store.get_stats()
            assert stats is not None
            assert "job_postings" in stats
            assert "resumes" in stats
            assert "company_analyses" in stats
            assert "search_sessions" in stats

    def test_save_and_search_job_posting(self) -> None:
        """Test saving and searching job postings."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import (
            JobSearchVectorStore,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobSearchVectorStore(persist_directory=tmpdir)
            
            # Save a job posting
            doc_id = store.save_job_posting(
                title="Software Engineer",
                company="TestCorp",
                content="Build software systems",
                analysis="Good match for Python developers",
                url="https://example.com/job",
                match_score=85.0
            )
            assert doc_id is not None
            
            # Search for it
            results = store.search_job_postings("software engineer", n_results=5)
            assert len(results) >= 1

    def test_save_and_search_resume(self) -> None:
        """Test saving and searching resumes."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import (
            JobSearchVectorStore,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobSearchVectorStore(persist_directory=tmpdir)
            
            # Save a resume
            doc_id = store.save_resume(
                target_role="Data Scientist",
                target_company="DataCo",
                resume_content="Experienced data scientist with ML skills",
                source_profile="5 years Python, ML, statistics",
                optimization_score=90.0
            )
            assert doc_id is not None
            
            # Search for it
            results = store.search_resumes("data scientist", n_results=5)
            assert len(results) >= 1

    def test_save_and_get_company_analysis(self) -> None:
        """Test saving and retrieving company analysis."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import (
            JobSearchVectorStore,
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JobSearchVectorStore(persist_directory=tmpdir)
            
            # Save company analysis
            doc_id = store.save_company_analysis(
                company_name="TechStartup",
                analysis="Great culture, fast-paced environment",
                rating=4.2,
                values=["Innovation", "Collaboration"]
            )
            assert doc_id is not None
            
            # Retrieve it
            result = store.get_company_analysis("TechStartup")
            assert result is not None
            assert result.get("found", True)  # In-memory store returns directly

    def test_history_tools_functions(self) -> None:
        """Test history tool functions work correctly."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_job_posting,
            save_resume,
            save_company_analysis,
            search_job_postings,
            get_history_stats,
        )
        
        # Test save functions return success
        result = save_job_posting(
            title="Test Job",
            company="Test Company",
            content="Test content",
            analysis="Test analysis"
        )
        assert result["success"] is True
        
        # Test search functions return results structure
        results = search_job_postings("test", n_results=5)
        assert "results" in results
        assert "count" in results
        
        # Test stats function
        stats = get_history_stats()
        assert "job_postings" in stats

    def test_user_profile_functions(self) -> None:
        """Test user profile storage functions."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            get_primary_profile,
            list_user_profiles,
        )
        
        # Save a profile
        result = save_user_profile(
            name="Test Profile",
            profile_content="5 years Python experience",
            skills='["Python", "AWS"]',
            experience_years=5,
            is_primary=True
        )
        assert result["success"] is True
        
        # Get primary profile
        primary = get_primary_profile()
        assert "found" in primary or "profile" in primary
        
        # List profiles
        profiles = list_user_profiles()
        assert "results" in profiles
        assert "count" in profiles

    def test_resume_version_functions(self) -> None:
        """Test resume version storage functions."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_resume_version,
            list_resume_versions,
            get_master_resume,
        )
        
        # Save a resume version
        result = save_resume_version(
            version_name="Technical Focus",
            target_role="Software Engineer",
            resume_content="Technical resume content",
            version_descriptor="Emphasizes technical skills",
            is_master=True
        )
        assert result["success"] is True
        
        # Get master resume
        master = get_master_resume()
        assert "found" in master or "resume" in master
        
        # List versions
        versions = list_resume_versions()
        assert "results" in versions
        assert "count" in versions

    def test_cover_letter_functions(self) -> None:
        """Test cover letter storage functions."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_cover_letter,
            get_cover_letters_for_company,
            search_cover_letters,
        )
        
        # Save a cover letter
        result = save_cover_letter(
            target_role="Software Engineer",
            target_company="TechCorp",
            cover_letter_content="Dear Hiring Manager...",
            tone="professional"
        )
        assert result["success"] is True
        
        # Get cover letters for company
        letters = get_cover_letters_for_company("TechCorp")
        assert "results" in letters
        assert "count" in letters
        
        # Search cover letters
        search_results = search_cover_letters("software")
        assert "results" in search_results
        assert "count" in search_results

    def test_search_criteria_functions(self) -> None:
        """Test search criteria storage functions."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_search_criteria,
            list_search_criteria,
            get_default_search_criteria,
        )
        
        # Save search criteria
        result = save_search_criteria(
            name="Remote ML Jobs",
            role="Machine Learning Engineer",
            location="Remote",
            keywords='["Python", "ML", "TensorFlow"]',
            remote_preference="remote",
            is_default=True
        )
        assert result["success"] is True
        
        # Get default criteria
        default = get_default_search_criteria()
        assert "found" in default or "criteria" in default
        
        # List all criteria
        criteria = list_search_criteria()
        assert "results" in criteria
        assert "count" in criteria


class TestMCPTools:
    """Tests for MCP tool configuration."""

    def test_mcp_tools_import(self) -> None:
        """Test MCP tools can be imported."""
        from job_agent_coordinator.tools.mcp_tools import (
            get_glassdoor_jobs_mcp,
            get_glassdoor_company_mcp,
            get_glassdoor_company_search_mcp,
            get_glassdoor_tools,
            get_jobspy_mcp,
            get_indeed_jobs_mcp,
        )
        assert get_glassdoor_jobs_mcp is not None
        assert get_glassdoor_company_mcp is not None
        assert get_glassdoor_company_search_mcp is not None
        assert get_glassdoor_tools is not None
        assert get_jobspy_mcp is not None
        assert get_indeed_jobs_mcp is not None

    def test_jobspy_mcp_returns_none(self) -> None:
        """Test JobSpy MCP returns None (disabled)."""
        from job_agent_coordinator.tools.mcp_tools import get_jobspy_mcp
        # JobSpy MCP is disabled (npm package doesn't exist)
        result = get_jobspy_mcp()
        assert result is None

    def test_platform_search_agents_exist(self) -> None:
        """Test platform search agents are configured."""
        from job_agent_coordinator.agent import (
            linkedin_search_agent,
            indeed_search_agent,
            glassdoor_search_agent,
        )
        assert linkedin_search_agent.name == "linkedin_search_agent"
        assert linkedin_search_agent.output_key == "linkedin_search_results"
        
        assert indeed_search_agent.name == "indeed_search_agent"
        assert indeed_search_agent.output_key == "indeed_search_results"
        
        assert glassdoor_search_agent.name == "glassdoor_search_agent"
        assert glassdoor_search_agent.output_key == "glassdoor_search_results"


class TestWorkflowAgents:
    """Tests for workflow agents."""

    def test_parallel_job_analysis(self) -> None:
        """Test parallel job analysis agent configuration."""
        from job_agent_coordinator.agent import parallel_job_analysis
        assert parallel_job_analysis.name == "parallel_job_analysis"
        # Has 2 sub-agents: job_analysis_agent and company_analysis_agent
        assert len(parallel_job_analysis.sub_agents) == 2

    def test_analysis_synthesizer(self) -> None:
        """Test analysis synthesizer agent configuration."""
        from job_agent_coordinator.agent import analysis_synthesizer
        assert analysis_synthesizer.name == "analysis_synthesizer"
        assert analysis_synthesizer.output_key == "synthesized_recommendations"

    def test_job_analysis_agent(self) -> None:
        """Test job analysis agent configuration."""
        from job_agent_coordinator.agent import job_analysis_agent
        assert job_analysis_agent.name == "job_analysis_agent"
        assert job_analysis_agent.output_key == "job_analyses"

    def test_company_analysis_agent(self) -> None:
        """Test company analysis agent configuration."""
        from job_agent_coordinator.agent import company_analysis_agent
        assert company_analysis_agent.name == "company_analysis_agent"
        assert company_analysis_agent.output_key == "company_analyses"


class TestApplicationDesigner:
    """Tests for application designer agent."""

    def test_application_designer_import(self) -> None:
        """Test application designer can be imported."""
        from job_agent_coordinator.sub_agents.application_designer import application_designer_agent
        assert application_designer_agent is not None

    def test_application_designer_structure(self) -> None:
        """Test application designer has parallel document creation sub-agent."""
        from job_agent_coordinator.sub_agents.application_designer import application_designer_agent
        # Check it has sub_agents
        assert hasattr(application_designer_agent, 'sub_agents')
        # Has 1 sub-agent: parallel_document_creation (which contains resume + cover letter)
        assert len(application_designer_agent.sub_agents) == 1
        parallel_creation = application_designer_agent.sub_agents[0]
        assert parallel_creation.name == "parallel_document_creation"
        # The parallel agent should have 2 sub-agents
        assert len(parallel_creation.sub_agents) == 2

    def test_application_designer_has_pdf_tools(self) -> None:
        """Test application designer has PDF generation tools."""
        from job_agent_coordinator.sub_agents.application_designer import application_designer_agent
        # Check it has tools
        assert hasattr(application_designer_agent, 'tools')
        tool_names = [t.name for t in application_designer_agent.tools]
        # Should have PDF-related tools
        assert "generate_resume_pdf" in tool_names
        assert "generate_cover_letter_pdf" in tool_names
        assert "list_pdfs" in tool_names


class TestPDFTools:
    """Tests for PDF generation tools."""

    def test_pdf_tools_import(self) -> None:
        """Test PDF tools can be imported."""
        from job_agent_coordinator.tools.pdf_tools import (
            generate_resume_pdf,
            generate_cover_letter_pdf,
            list_generated_pdfs,
            is_pdf_generation_available,
            get_resume_template_presets,
            get_output_directory,
        )
        assert generate_resume_pdf is not None
        assert generate_cover_letter_pdf is not None
        assert list_generated_pdfs is not None

    def test_pdf_availability_check(self) -> None:
        """Test PDF availability check works."""
        from job_agent_coordinator.tools.pdf_tools import is_pdf_generation_available
        # Should return bool
        result = is_pdf_generation_available()
        assert isinstance(result, bool)

    def test_template_presets(self) -> None:
        """Test template presets are available."""
        from job_agent_coordinator.tools.pdf_tools import get_resume_template_presets
        presets = get_resume_template_presets()
        assert isinstance(presets, dict)
        # Should have standard templates
        assert "professional" in presets
        assert "compact" in presets
        assert "leadership" in presets
        assert "technical" in presets
        # Each preset should have name and styles
        for key, preset in presets.items():
            assert "name" in preset
            assert "styles" in preset
            assert "sections_order" in preset

    def test_output_directory(self) -> None:
        """Test output directory function."""
        from job_agent_coordinator.tools.pdf_tools import get_output_directory
        output_dir = get_output_directory()
        assert output_dir is not None
        assert "job_agent_coordinator" in output_dir
        assert "generated_pdfs" in output_dir


class TestResumeTemplates:
    """Tests for resume templates storage."""

    def test_resume_template_functions(self) -> None:
        """Test resume template functions exist in history manager."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_resume_template,
            get_resume_template,
            get_default_resume_template,
            list_resume_templates,
            delete_resume_template,
        )
        assert callable(save_resume_template)
        assert callable(get_resume_template)
        assert callable(get_default_resume_template)
        assert callable(list_resume_templates)
        assert callable(delete_resume_template)

    def test_design_instruction_functions(self) -> None:
        """Test design instruction functions exist in history manager."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_design_instruction,
            get_active_instructions,
            get_guard_rails,
            get_requirements,
            list_design_instructions,
            toggle_instruction,
            delete_design_instruction,
        )
        assert callable(save_design_instruction)
        assert callable(get_active_instructions)
        assert callable(get_guard_rails)
        assert callable(get_requirements)
        assert callable(list_design_instructions)
        assert callable(toggle_instruction)
        assert callable(delete_design_instruction)

    def test_vector_store_has_template_collections(self) -> None:
        """Test vector store has template and instruction collections."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import JobSearchVectorStore
        store = JobSearchVectorStore()
        stats = store.get_stats()
        # Should have the new collections
        assert "resume_templates" in stats
        assert "design_instructions" in stats


class TestCoverLetterWriter:
    """Tests for cover letter writer with PDF capability."""

    def test_cover_letter_writer_import(self) -> None:
        """Test cover letter writer can be imported."""
        from job_agent_coordinator.sub_agents.cover_letter_writer import cover_letter_writer_agent
        assert cover_letter_writer_agent is not None

    def test_cover_letter_writer_has_pdf_tool(self) -> None:
        """Test cover letter writer has PDF generation tool."""
        from job_agent_coordinator.sub_agents.cover_letter_writer import cover_letter_writer_agent
        tool_names = [t.name for t in cover_letter_writer_agent.tools]
        assert "generate_cover_letter_pdf" in tool_names
        assert "check_pdf_available" in tool_names


class TestProfileStorage:
    """Comprehensive tests for user profile storage functionality."""

    def test_save_and_retrieve_profile(self) -> None:
        """Test saving and retrieving a complete user profile."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            get_user_profile,
            delete_user_profile,
        )
        
        # Save a complete profile
        result = save_user_profile(
            name="Full Stack Developer Profile",
            profile_content="""
            Experienced full-stack developer with 8 years of experience.
            Currently a Senior Software Engineer at TechCorp.
            Expertise in Python, React, AWS, and distributed systems.
            Led team of 5 engineers on cloud migration project.
            """,
            skills='["Python", "React", "AWS", "Docker", "Kubernetes", "PostgreSQL"]',
            experience_years=8,
            current_role="Senior Software Engineer",
            target_roles='["Staff Engineer", "Principal Engineer", "Engineering Manager"]',
            education='["M.S. Computer Science - Stanford", "B.S. Computer Engineering - MIT"]',
            certifications='["AWS Solutions Architect", "Kubernetes Administrator"]',
            achievements='["Led cloud migration saving $2M/year", "Reduced latency by 40%", "Mentored 10 junior engineers"]',
            values='["innovation", "collaboration", "continuous learning"]',
            work_preferences='{"remote": true, "location": "San Francisco Bay Area", "salary_min": 200000}',
            is_primary=True
        )
        
        assert result["success"] is True
        assert "id" in result
        profile_id = result["id"]
        
        # Retrieve the profile - data is in metadata dict
        retrieved = get_user_profile(profile_id)
        assert retrieved["found"] is True
        assert "profile" in retrieved
        profile = retrieved["profile"]
        # Profile structure: {"id": ..., "document": ..., "metadata": {...}}
        metadata = profile.get("metadata", profile)  # Handle both formats
        assert metadata.get("name") == "Full Stack Developer Profile"
        assert metadata.get("experience_years") == 8
        assert metadata.get("current_role") == "Senior Software Engineer"
        
        # Clean up
        delete_result = delete_user_profile(profile_id)
        assert delete_result["success"] is True

    def test_primary_profile_workflow(self) -> None:
        """Test the primary profile designation workflow."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            get_primary_profile,
            update_user_profile,
            delete_user_profile,
        )
        
        # Save first profile as primary
        result1 = save_user_profile(
            name="Profile A",
            profile_content="First profile",
            experience_years=5,
            is_primary=True
        )
        assert result1["success"] is True
        profile_a_id = result1["id"]
        
        # Save second profile as primary (should become new primary)
        result2 = save_user_profile(
            name="Profile B",
            profile_content="Second profile",
            experience_years=10,
            is_primary=True
        )
        assert result2["success"] is True
        profile_b_id = result2["id"]
        
        # Get primary - should be Profile B
        primary = get_primary_profile()
        if primary.get("found"):
            profile = primary["profile"]
            metadata = profile.get("metadata", profile)
            assert metadata.get("name") == "Profile B"
        
        # Clean up
        delete_user_profile(profile_a_id)
        delete_user_profile(profile_b_id)

    def test_update_profile(self) -> None:
        """Test updating an existing profile."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            update_user_profile,
            get_user_profile,
            delete_user_profile,
        )
        
        # Create profile
        result = save_user_profile(
            name="Updatable Profile",
            profile_content="Original content",
            experience_years=3,
            current_role="Junior Developer"
        )
        profile_id = result["id"]
        
        # Update profile
        update_result = update_user_profile(
            profile_id=profile_id,
            experience_years=5,
            current_role="Senior Developer",
            skills='["Python", "Go", "Rust"]'
        )
        assert update_result["success"] is True
        
        # Verify update
        updated = get_user_profile(profile_id)
        assert updated["found"] is True
        profile = updated["profile"]
        metadata = profile.get("metadata", profile)
        assert metadata.get("experience_years") == 5
        assert metadata.get("current_role") == "Senior Developer"
        
        # Clean up
        delete_user_profile(profile_id)

    def test_search_profiles(self) -> None:
        """Test searching profiles by skills and content."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            search_user_profiles,
            delete_user_profile,
        )
        
        # Create profiles with different skills
        profile_ids = []
        
        result1 = save_user_profile(
            name="Python Developer",
            profile_content="Expert Python developer with Django and FastAPI experience",
            skills='["Python", "Django", "FastAPI", "PostgreSQL"]',
            experience_years=6
        )
        profile_ids.append(result1["id"])
        
        result2 = save_user_profile(
            name="Go Developer",
            profile_content="Go backend developer specializing in microservices",
            skills='["Go", "gRPC", "Kubernetes", "PostgreSQL"]',
            experience_years=4
        )
        profile_ids.append(result2["id"])
        
        result3 = save_user_profile(
            name="Full Stack Developer",
            profile_content="Full stack with React and Python",
            skills='["Python", "React", "TypeScript", "Node.js"]',
            experience_years=5
        )
        profile_ids.append(result3["id"])
        
        # Search for Python profiles
        search_results = search_user_profiles("Python developer", n_results=10)
        assert "results" in search_results
        # Should find at least the Python-related profiles
        
        # Clean up
        for pid in profile_ids:
            delete_user_profile(pid)

    def test_list_all_profiles(self) -> None:
        """Test listing all profiles."""
        from job_agent_coordinator.sub_agents.history_manager.agent import (
            save_user_profile,
            list_user_profiles,
            delete_user_profile,
        )
        
        # Create a few profiles
        ids = []
        for i in range(3):
            result = save_user_profile(
                name=f"Test Profile {i}",
                profile_content=f"Content for profile {i}",
                experience_years=i + 1
            )
            ids.append(result["id"])
        
        # List profiles
        listed = list_user_profiles()
        assert "results" in listed
        assert "count" in listed
        assert listed["count"] >= 3
        
        # Clean up
        for pid in ids:
            delete_user_profile(pid)

    def test_profile_analyst_has_storage_tools(self) -> None:
        """Test that profile analyst agent has profile storage tools."""
        from job_agent_coordinator.sub_agents.profile_analyst import profile_analyst_agent
        
        tool_names = [t.name for t in profile_analyst_agent.tools]
        
        # Check for profile storage tools
        assert "save_user_profile" in tool_names
        assert "get_primary_profile" in tool_names
        assert "get_user_profile" in tool_names
        assert "list_user_profiles" in tool_names
        assert "update_user_profile" in tool_names
        assert "search_user_profiles" in tool_names

    def test_vector_store_profile_methods(self) -> None:
        """Test vector store profile methods directly."""
        from job_agent_coordinator.sub_agents.history_manager.vector_store import JobSearchVectorStore
        
        store = JobSearchVectorStore()
        
        # Save profile
        profile_id = store.save_user_profile(
            name="Direct Store Test",
            profile_content="Testing vector store directly",
            skills=["Testing", "QA"],
            experience_years=3,
            is_primary=False
        )
        assert profile_id is not None
        
        # Get profile - returns {"id": ..., "document": ..., "metadata": {...}}
        profile = store.get_user_profile(profile_id)
        assert profile is not None
        metadata = profile.get("metadata", profile)
        assert metadata.get("name") == "Direct Store Test"
        
        # Update profile
        success = store.update_user_profile(
            profile_id=profile_id,
            experience_years=5
        )
        assert success is True
        
        # Verify update
        updated = store.get_user_profile(profile_id)
        updated_meta = updated.get("metadata", updated)
        assert updated_meta.get("experience_years") == 5
        
        # Delete profile
        deleted = store.delete_user_profile(profile_id)
        assert deleted is True
        
        # Verify deletion
        gone = store.get_user_profile(profile_id)
        assert gone is None
