"""
Unit tests for exclusion list enforcement.

Tests:
1. list_matches() filters excluded companies
2. Exclusion matching is case-insensitive
3. Exclusion matches partial company names (e.g., "Amazon" matches "Amazon.com")
4. Job matcher marks excluded companies correctly
5. show_top_matches excludes companies
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_profile_with_exclusions():
    """Sample user profile with exclusion list."""
    return {
        "name": "Test User",
        "location": "Seattle, WA",
        "skills": ["python", "java", "kubernetes"],
        "target_roles": ["software engineer"],
        "target_locations": ["seattle"],
        "remote_preference": "hybrid",
        "excluded_companies": ["Amazon", "Meta", "Apple"],
        "resume_summary": "Test profile.",
    }


@pytest.fixture
def sample_jobs():
    """Sample jobs including some from excluded companies."""
    return {
        "job1": {
            "id": "job1",
            "title": "Software Engineer",
            "company": "Amazon.com",
            "location": "Seattle, WA",
            "description": "Work at Amazon",
            "url": "https://amazon.jobs/123",
        },
        "job2": {
            "id": "job2",
            "title": "Software Engineer",
            "company": "Google",
            "location": "Seattle, WA",
            "description": "Work at Google",
            "url": "https://google.com/jobs/123",
        },
        "job3": {
            "id": "job3",
            "title": "Software Engineer",
            "company": "Meta Platforms",
            "location": "Seattle, WA",
            "description": "Work at Meta",
            "url": "https://meta.com/jobs/123",
        },
        "job4": {
            "id": "job4",
            "title": "Software Engineer",
            "company": "Microsoft",
            "location": "Seattle, WA",
            "description": "Work at Microsoft",
            "url": "https://microsoft.com/jobs/123",
        },
        "job5": {
            "id": "job5",
            "title": "Software Engineer",
            "company": "APPLE INC",  # Test case-insensitive
            "location": "Seattle, WA",
            "description": "Work at Apple",
            "url": "https://apple.com/jobs/123",
        },
    }


@pytest.fixture
def sample_matches(sample_jobs):
    """Sample matches including excluded companies."""
    return {
        "job1:profile1": {
            "job_id": "job1",
            "match_score": 75,
            "keyword_score": 70,
            "llm_score": 80,
            "combined_score": 75,
            "match_level": "good",
        },
        "job2:profile1": {
            "job_id": "job2",
            "match_score": 80,
            "keyword_score": 75,
            "llm_score": 85,
            "combined_score": 80,
            "match_level": "strong",
        },
        "job3:profile1": {
            "job_id": "job3",
            "match_score": 70,
            "keyword_score": 65,
            "llm_score": 75,
            "combined_score": 70,
            "match_level": "good",
        },
        "job4:profile1": {
            "job_id": "job4",
            "match_score": 85,
            "keyword_score": 80,
            "llm_score": 90,
            "combined_score": 85,
            "match_level": "strong",
        },
        "job5:profile1": {
            "job_id": "job5",
            "match_score": 65,
            "keyword_score": 60,
            "llm_score": 70,
            "combined_score": 65,
            "match_level": "moderate",
        },
    }


# =============================================================================
# TEST: _is_company_excluded helper function
# =============================================================================

class TestIsCompanyExcluded:
    """Tests for the _is_company_excluded helper method."""
    
    def test_exact_match(self):
        """Test exact company name match."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {"job1": {"company": "Amazon"}}
        cache._matches = {}
        
        match = {"job_id": "job1"}
        excluded = ["amazon"]
        
        result = cache._is_company_excluded(match, excluded)
        assert result is True
    
    def test_partial_match(self):
        """Test partial company name match (e.g., 'Amazon' matches 'Amazon.com')."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {"job1": {"company": "Amazon.com Services"}}
        cache._matches = {}
        
        match = {"job_id": "job1"}
        excluded = ["amazon"]
        
        result = cache._is_company_excluded(match, excluded)
        assert result is True
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {"job1": {"company": "AMAZON INC"}}
        cache._matches = {}
        
        match = {"job_id": "job1"}
        excluded = ["amazon"]
        
        result = cache._is_company_excluded(match, excluded)
        assert result is True
    
    def test_no_match(self):
        """Test non-excluded company."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {"job1": {"company": "Google"}}
        cache._matches = {}
        
        match = {"job_id": "job1"}
        excluded = ["amazon", "meta", "apple"]
        
        result = cache._is_company_excluded(match, excluded)
        assert result is False
    
    def test_empty_exclusions(self):
        """Test with no exclusions."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {"job1": {"company": "Amazon"}}
        cache._matches = {}
        
        match = {"job_id": "job1"}
        excluded = []
        
        result = cache._is_company_excluded(match, excluded)
        assert result is False
    
    def test_missing_job(self):
        """Test with job not found in cache."""
        from job_agent_coordinator.tools.job_cache import JobCache
        
        cache = JobCache.__new__(JobCache)
        cache._jobs = {}
        cache._matches = {}
        
        match = {"job_id": "nonexistent"}
        excluded = ["amazon"]
        
        result = cache._is_company_excluded(match, excluded)
        assert result is False


# =============================================================================
# TEST: list_matches with exclusions
# =============================================================================

class TestListMatchesExclusions:
    """Tests for list_matches() exclusion filtering."""
    
    def test_filters_excluded_companies(self, sample_jobs, sample_matches, sample_profile_with_exclusions):
        """Verify list_matches filters out excluded companies."""
        from job_agent_coordinator.tools.job_cache import JobCache
        from job_agent_coordinator.tools import profile_store
        
        # Create cache with sample data
        cache = JobCache.__new__(JobCache)
        cache._jobs = sample_jobs
        cache._matches = sample_matches
        
        # Mock profile store
        with patch.object(profile_store, 'get_store') as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_search_context.return_value = sample_profile_with_exclusions
            mock_get_store.return_value = mock_store
            
            # Get matches - should filter Amazon, Meta, Apple
            matches = cache.list_matches(min_score=0, limit=100)
        
        # Should only return Google and Microsoft (job2 and job4)
        assert len(matches) == 2
        
        companies = [sample_jobs[m["job_id"]]["company"] for m in matches]
        assert "Amazon.com" not in companies
        assert "Meta Platforms" not in companies
        assert "APPLE INC" not in companies
        assert "Google" in companies
        assert "Microsoft" in companies
    
    def test_filters_already_marked_excluded(self, sample_jobs):
        """Verify list_matches filters matches already marked as excluded."""
        from job_agent_coordinator.tools.job_cache import JobCache
        from job_agent_coordinator.tools import profile_store
        
        # Create cache with a match marked as excluded
        cache = JobCache.__new__(JobCache)
        cache._jobs = sample_jobs
        cache._matches = {
            "job1:profile1": {
                "job_id": "job1",
                "match_score": 0,
                "match_level": "excluded",  # Already marked excluded
            },
            "job2:profile1": {
                "job_id": "job2",
                "match_score": 80,
                "match_level": "strong",
            },
        }
        
        # Mock profile store with no exclusions
        with patch.object(profile_store, 'get_store') as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_search_context.return_value = {"excluded_companies": []}
            mock_get_store.return_value = mock_store
            
            # Get matches
            matches = cache.list_matches(min_score=0, limit=100)
        
        # Should only return job2
        assert len(matches) == 1
        assert matches[0]["job_id"] == "job2"
    
    def test_no_exclusions_returns_all(self, sample_jobs, sample_matches):
        """Verify list_matches returns all when no exclusions."""
        from job_agent_coordinator.tools.job_cache import JobCache
        from job_agent_coordinator.tools import profile_store
        
        # Create cache with sample data
        cache = JobCache.__new__(JobCache)
        cache._jobs = sample_jobs
        cache._matches = sample_matches
        
        # Mock profile store with no exclusions
        with patch.object(profile_store, 'get_store') as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_search_context.return_value = {"excluded_companies": []}
            mock_get_store.return_value = mock_store
            
            # Get matches
            matches = cache.list_matches(min_score=0, limit=100)
        
        # Should return all 5 matches
        assert len(matches) == 5


# =============================================================================
# TEST: Job matcher exclusion marking
# =============================================================================

class TestJobMatcherExclusions:
    """Tests for job matcher exclusion marking."""
    
    def test_keyword_match_marks_excluded(self, sample_profile_with_exclusions):
        """Verify keyword_match marks excluded companies correctly."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import keyword_match
        
        result = keyword_match(
            job_description="Work at Amazon on cloud services",
            job_title="Software Engineer",
            company="Amazon",
            location="Seattle",
            profile=sample_profile_with_exclusions,
        )
        
        assert result.get("excluded") is True
        assert result.get("match_level") == "excluded"
        assert result.get("keyword_score") == 0
        assert "exclusion" in result.get("reason", "").lower()
    
    def test_keyword_match_not_excluded(self, sample_profile_with_exclusions):
        """Verify keyword_match doesn't mark non-excluded companies."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import keyword_match
        
        result = keyword_match(
            job_description="Work at Google on cloud services with Python and Kubernetes",
            job_title="Software Engineer",
            company="Google",
            location="Seattle",
            profile=sample_profile_with_exclusions,
        )
        
        assert result.get("excluded") is not True
        assert result.get("match_level") != "excluded"
        assert result.get("keyword_score") > 0


# =============================================================================
# TEST: Case sensitivity and variations
# =============================================================================

class TestExclusionCaseSensitivity:
    """Tests for case-insensitive exclusion matching."""
    
    def test_various_amazon_formats(self, sample_profile_with_exclusions):
        """Test exclusion works with various company name formats."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import keyword_match
        
        company_variants = [
            "Amazon",
            "AMAZON",
            "amazon",
            "Amazon.com",
            "Amazon Web Services",
            "Amazon Inc",
        ]
        
        for company in company_variants:
            result = keyword_match(
                job_description="Work on cloud services",
                job_title="Software Engineer",
                company=company,
                location="Seattle",
                profile=sample_profile_with_exclusions,
            )
            assert result.get("excluded") is True, f"Should exclude '{company}'"
    
    def test_meta_variants(self, sample_profile_with_exclusions):
        """Test exclusion works with Meta company name variants."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import keyword_match
        
        company_variants = [
            "Meta",
            "META",
            "Meta Platforms",
            "Meta Platforms, Inc.",
        ]
        
        for company in company_variants:
            result = keyword_match(
                job_description="Work on social media",
                job_title="Software Engineer",
                company=company,
                location="Seattle",
                profile=sample_profile_with_exclusions,
            )
            assert result.get("excluded") is True, f"Should exclude '{company}'"


# =============================================================================
# TEST: Integration - full pipeline exclusion
# =============================================================================

class TestExclusionIntegration:
    """Integration-style tests for exclusion across pipeline."""
    
    def test_analyze_job_match_respects_exclusions(self, sample_profile_with_exclusions):
        """Test that analyze_job_match respects exclusion list."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match
        from job_agent_coordinator.tools import profile_store
        
        with patch.object(profile_store, 'get_store') as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_search_context.return_value = sample_profile_with_exclusions
            mock_get_store.return_value = mock_store
            
            # Test excluded company
            result = analyze_job_match(
                job_title="Software Engineer",
                company="Amazon",
                job_description="Cloud services role",
                location="Seattle",
                salary_info="",
                job_url="https://amazon.jobs/123",
                job_id="test_amazon",
                use_cache=False,
                run_llm=False,
            )
            
            # Verify exclusion is applied
            assert result.get("match_level") == "excluded"
            assert result.get("keyword_score") == 0
            assert result.get("combined_score") == 0
    
    def test_analyze_job_match_allows_non_excluded(self, sample_profile_with_exclusions):
        """Test that analyze_job_match allows non-excluded companies."""
        from job_agent_coordinator.sub_agents.job_matcher.agent import analyze_job_match
        from job_agent_coordinator.tools import profile_store
        
        with patch.object(profile_store, 'get_store') as mock_get_store:
            mock_store = MagicMock()
            mock_store.get_search_context.return_value = sample_profile_with_exclusions
            mock_get_store.return_value = mock_store
            
            # Test non-excluded company
            result = analyze_job_match(
                job_title="Software Engineer",
                company="Netflix",
                job_description="Streaming services role with Python and Kubernetes",
                location="Seattle",
                salary_info="",
                job_url="https://netflix.jobs/123",
                job_id="test_netflix",
                use_cache=False,
                run_llm=False,
            )
            
            assert result.get("match_level") != "excluded"
            assert result.get("excluded") is not True
            assert result.get("keyword_score", 0) > 0


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
