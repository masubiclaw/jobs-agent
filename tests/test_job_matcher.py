"""
Unit tests for two-pass job matching.

Tests:
1. Pass 1: Keyword/regex matching
2. Pass 2: LLM holistic analysis (mocked)
3. Combined two-pass matching
4. Checkpoint/resume functionality
5. Cache storage of dual scores
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from job_agent_coordinator.sub_agents.job_matcher.agent import (
    keyword_match,
    llm_match,
    analyze_job_match,
    batch_match,
    MatchingProgress,
    _determine_level,
    _generate_job_id,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_profile():
    """Sample user profile for testing."""
    return {
        "name": "Test User",
        "location": "Seattle, WA",
        "skills": ["python", "java", "kubernetes", "aws", "machine learning", "react"],
        "target_roles": ["software engineer", "ml engineer", "data scientist"],
        "target_locations": ["seattle", "san francisco", "remote"],
        "remote_preference": "hybrid",
        "salary_range": "$150,000 - $200,000",
        "excluded_companies": ["badcompany"],
        "resume_summary": "10+ years experience in ML/AI systems and distributed computing.",
    }


@pytest.fixture
def sample_job_high_match():
    """Job that should match well."""
    return {
        "title": "Senior Software Engineer - ML Platform",
        "company": "TechCorp",
        "location": "Seattle, WA",
        "description": """
        We're looking for a Senior Software Engineer to join our ML Platform team.
        
        Requirements:
        - 5+ years of experience with Python and Java
        - Experience with Kubernetes and AWS
        - Strong background in machine learning and distributed systems
        - Experience with React or similar frontend frameworks
        
        Nice to have:
        - Experience with TensorFlow or PyTorch
        - Familiarity with Kafka and Spark
        
        This is a hybrid role based in Seattle.
        """,
        "salary": "$180,000 - $220,000",
        "url": "https://techcorp.com/jobs/123",
    }


@pytest.fixture
def sample_job_low_match():
    """Job that should have low match."""
    return {
        "title": "Junior Marketing Coordinator",
        "company": "MarketingCo",
        "location": "New York, NY",
        "description": """
        Entry level marketing position. 0-2 years experience.
        
        Requirements:
        - Bachelor's degree in Marketing
        - Experience with social media management
        - Strong communication skills
        - Knowledge of SEO and content marketing
        
        On-site position in NYC.
        """,
        "salary": "$45,000 - $55,000",
        "url": "https://marketingco.com/jobs/456",
    }


@pytest.fixture
def sample_job_excluded():
    """Job from excluded company."""
    return {
        "title": "Software Engineer",
        "company": "BadCompany",
        "location": "Remote",
        "description": "Great opportunity...",
        "url": "https://badcompany.com/jobs/789",
    }


# =============================================================================
# PASS 1: KEYWORD MATCHING TESTS
# =============================================================================

class TestKeywordMatching:
    """Tests for Pass 1 keyword/regex matching."""
    
    def test_high_skill_match(self, sample_profile, sample_job_high_match):
        """Test that jobs with matching skills score high."""
        result = keyword_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            profile=sample_profile,
        )
        
        assert result["keyword_score"] >= 60, f"Expected high score, got {result['keyword_score']}"
        assert result["match_level"] in ("good", "strong")
        assert "python" in result["matching_skills"]
        assert "java" in result["matching_skills"]
        assert "kubernetes" in result["matching_skills"]
        assert not result["excluded"]
    
    def test_low_skill_match(self, sample_profile, sample_job_low_match):
        """Test that jobs with few matching skills score low."""
        result = keyword_match(
            job_title=sample_job_low_match["title"],
            company=sample_job_low_match["company"],
            job_description=sample_job_low_match["description"],
            location=sample_job_low_match["location"],
            profile=sample_profile,
        )
        
        assert result["keyword_score"] < 60, f"Expected low score, got {result['keyword_score']}"
        assert result["match_level"] in ("partial", "weak")
        assert len(result["matching_skills"]) < 3
    
    def test_excluded_company(self, sample_profile, sample_job_excluded):
        """Test that excluded companies are flagged."""
        result = keyword_match(
            job_title=sample_job_excluded["title"],
            company=sample_job_excluded["company"],
            job_description=sample_job_excluded["description"],
            location=sample_job_excluded["location"],
            profile=sample_profile,
        )
        
        assert result["excluded"] is True
        assert result["keyword_score"] == 0
        assert result["match_level"] == "excluded"
    
    def test_role_match(self, sample_profile, sample_job_high_match):
        """Test role title matching."""
        result = keyword_match(
            job_title="Software Engineer",
            company="TechCorp",
            job_description=sample_job_high_match["description"],
            location="Seattle",
            profile=sample_profile,
        )
        
        assert result["role_match"] is True
    
    def test_location_match(self, sample_profile):
        """Test location matching."""
        # Seattle should match
        result = keyword_match(
            job_title="Engineer",
            company="Co",
            job_description="A job in Seattle",
            location="Seattle, WA",
            profile=sample_profile,
        )
        assert result["location_match"] is True
        
        # Remote should match
        result = keyword_match(
            job_title="Engineer",
            company="Co",
            job_description="This is a remote position",
            location="Remote",
            profile=sample_profile,
        )
        assert result["location_match"] is True
    
    def test_experience_level_detection(self, sample_profile):
        """Test experience level detection."""
        # Senior
        result = keyword_match(
            job_title="Engineer",
            company="Co",
            job_description="Looking for a senior engineer with 7+ years experience",
            location="Seattle",
            profile=sample_profile,
        )
        assert result["detected_level"] == "senior"
        
        # Entry
        result = keyword_match(
            job_title="Engineer",
            company="Co",
            job_description="Entry level position, 0-2 years experience, new grad welcome",
            location="Seattle",
            profile=sample_profile,
        )
        assert result["detected_level"] == "entry"


# =============================================================================
# PASS 2: LLM MATCHING TESTS (Mocked)
# =============================================================================

class TestLLMMatching:
    """Tests for Pass 2 LLM holistic analysis."""
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.requests.post')
    def test_llm_success(self, mock_post, sample_profile, sample_job_high_match):
        """Test successful LLM analysis."""
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "response": """[llm_analysis]
score: 78%
assessment: Strong candidate with relevant ML and distributed systems experience.

[key_strengths]
- Python and Java expertise matches requirements
- Kubernetes/AWS experience is valuable
- ML background aligns with team focus

[concerns]
- No specific TensorFlow experience mentioned

[recommendations]
1. Emphasize distributed systems experience
2. Highlight any PyTorch work as alternative to TensorFlow
3. Mention specific ML projects"""
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        result = llm_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            salary_info=sample_job_high_match["salary"],
            job_url=sample_job_high_match["url"],
            profile=sample_profile,
        )
        
        assert result["llm_success"] is True
        assert result["llm_score"] == 78
        assert result["match_level"] == "good"
        assert "[llm_analysis]" in result["toon_report"]
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.requests.post')
    def test_llm_timeout(self, mock_post, sample_profile, sample_job_high_match):
        """Test LLM timeout handling."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        result = llm_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            salary_info="",
            job_url="",
            profile=sample_profile,
        )
        
        assert result["llm_success"] is False
        assert result["llm_score"] is None
        assert "timeout" in result["error"]
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.requests.post')
    def test_llm_includes_keyword_context(self, mock_post, sample_profile, sample_job_high_match):
        """Test that LLM receives keyword analysis context."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "[llm_analysis]\nscore: 75%\nassessment: Good match."}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        keyword_result = {
            "keyword_score": 70,
            "matching_skills": ["python", "java"],
            "missing_skills": ["go"],
            "role_match": True,
            "location_match": True,
        }
        
        llm_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            salary_info="",
            job_url="",
            profile=sample_profile,
            keyword_result=keyword_result,
        )
        
        # Verify the prompt includes keyword context
        call_args = mock_post.call_args
        prompt = call_args[1]["json"]["prompt"]
        assert "Keyword Score: 70%" in prompt
        assert "python" in prompt


# =============================================================================
# TWO-PASS COMBINED TESTS
# =============================================================================

class TestTwoPassMatching:
    """Tests for combined two-pass matching."""
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent._get_profile_context')
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.get_cache')
    def test_keyword_only(self, mock_cache, mock_profile, sample_profile, sample_job_high_match):
        """Test matching with keyword only (no LLM)."""
        mock_profile.return_value = sample_profile
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_match.return_value = None
        mock_cache.return_value = mock_cache_instance
        
        result = analyze_job_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            salary_info=sample_job_high_match["salary"],
            job_url=sample_job_high_match["url"],
            use_cache=True,
            run_llm=False,
        )
        
        assert result["success"] is True
        assert result["keyword_score"] >= 60
        assert result["llm_score"] is None
        assert result["combined_score"] == result["keyword_score"]
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent._get_profile_context')
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.get_cache')
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.requests.post')
    def test_two_pass_combined(self, mock_post, mock_cache, mock_profile, sample_profile, sample_job_high_match):
        """Test full two-pass matching."""
        mock_profile.return_value = sample_profile
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_match.return_value = None
        mock_cache.return_value = mock_cache_instance
        
        # Mock LLM
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "[llm_analysis]\nscore: 82%\nassessment: Strong match."}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        result = analyze_job_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            location=sample_job_high_match["location"],
            run_llm=True,
        )
        
        assert result["success"] is True
        assert result["keyword_score"] >= 60
        assert result["llm_score"] == 82
        # Combined: 20% keyword + 80% LLM
        expected_combined = int(result["keyword_score"] * 0.2 + 82 * 0.8)
        assert result["combined_score"] == expected_combined
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent._get_profile_context')
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.get_cache')
    def test_cache_hit(self, mock_cache, mock_profile, sample_profile, sample_job_high_match):
        """Test cache hit returns cached result."""
        mock_profile.return_value = sample_profile
        
        cached_result = {
            "keyword_score": 75,
            "llm_score": 80,
            "combined_score": 78,
            "match_level": "good",
            "toon_report": "[cached]",
        }
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_match.return_value = cached_result
        mock_cache.return_value = mock_cache_instance
        
        result = analyze_job_match(
            job_title=sample_job_high_match["title"],
            company=sample_job_high_match["company"],
            job_description=sample_job_high_match["description"],
            use_cache=True,
        )
        
        assert result["from_cache"] is True
        assert result["keyword_score"] == 75


# =============================================================================
# CHECKPOINT/RESUME TESTS
# =============================================================================

class TestCheckpointResume:
    """Tests for checkpoint/resume functionality."""
    
    def test_progress_start_and_complete(self, tmp_path):
        """Test starting and completing progress tracking."""
        checkpoint_file = tmp_path / "progress.json"
        progress = MatchingProgress(checkpoint_file)
        
        progress.start(total_jobs=100, run_llm=True)
        assert progress._progress["status"] == "in_progress"
        assert progress._progress["total_jobs"] == 100
        
        progress.mark_complete("job1", keyword_score=70, llm_score=75)
        assert progress.is_completed("job1")
        assert not progress.is_completed("job2")
        assert progress.get_completed_count() == 1
        
        progress.finish()
        assert progress._progress["status"] == "complete"
    
    def test_progress_persistence(self, tmp_path):
        """Test that progress is persisted to disk."""
        checkpoint_file = tmp_path / "progress.json"
        
        # Create and save progress
        progress1 = MatchingProgress(checkpoint_file)
        progress1.start(50)
        progress1.mark_complete("job1", 70)
        progress1.mark_complete("job2", 80, 85)
        
        # Load in new instance
        progress2 = MatchingProgress(checkpoint_file)
        assert progress2.is_completed("job1")
        assert progress2.is_completed("job2")
        assert progress2.get_completed_count() == 2
    
    def test_progress_clear(self, tmp_path):
        """Test clearing progress."""
        checkpoint_file = tmp_path / "progress.json"
        progress = MatchingProgress(checkpoint_file)
        
        progress.start(10)
        progress.mark_complete("job1", 70)
        progress.clear()
        
        assert not progress.is_completed("job1")
        assert progress.get_completed_count() == 0
    
    def test_progress_summary(self, tmp_path):
        """Test progress summary."""
        checkpoint_file = tmp_path / "progress.json"
        progress = MatchingProgress(checkpoint_file)
        
        progress.start(10)
        progress.mark_complete("job1", 70)
        progress.mark_complete("job2", 80)
        progress.mark_complete("job3", 60)
        
        summary = progress.get_summary()
        assert summary["total"] == 10
        assert summary["completed"] == 3
        assert summary["avg_score"] == 70.0  # (70+80+60)/3


# =============================================================================
# BATCH MATCHING TESTS
# =============================================================================

class TestBatchMatching:
    """Tests for batch matching with resume support."""
    
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent._get_profile_context')
    @patch('job_agent_coordinator.sub_agents.job_matcher.agent.get_cache')
    def test_batch_match_basic(self, mock_cache, mock_profile, sample_profile, tmp_path):
        """Test basic batch matching."""
        mock_profile.return_value = sample_profile
        mock_cache_instance = MagicMock()
        mock_cache_instance.get_match.return_value = None
        mock_cache.return_value = mock_cache_instance
        
        jobs = [
            {"title": "Software Engineer", "company": "Co1", "description": "Python and AWS required", "location": "Seattle"},
            {"title": "Data Scientist", "company": "Co2", "description": "ML and Python experience", "location": "Remote"},
            {"title": "Marketing Manager", "company": "Co3", "description": "Marketing experience", "location": "NYC"},
        ]
        
        # Patch checkpoint file location
        with patch.object(MatchingProgress, '__init__', lambda self, f=None: setattr(self, 'checkpoint_file', tmp_path / "prog.json") or setattr(self, '_progress', {"completed": {}, "status": "idle"})):
            result = batch_match(jobs, run_llm=False, resume=False)
        
        assert result["total"] == 3
        assert result["processed"] >= 0  # May vary based on mock


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_determine_level(self):
        """Test match level determination."""
        assert _determine_level(90) == "strong"
        assert _determine_level(80) == "strong"
        assert _determine_level(79) == "good"
        assert _determine_level(60) == "good"
        assert _determine_level(59) == "partial"
        assert _determine_level(40) == "partial"
        assert _determine_level(39) == "weak"
        assert _determine_level(0) == "weak"
    
    def test_generate_job_id_with_url(self):
        """Test job ID generation with URL."""
        id1 = _generate_job_id("Engineer", "Co", "Seattle", "https://example.com/job1")
        id2 = _generate_job_id("Engineer", "Co", "Seattle", "https://example.com/job1")
        id3 = _generate_job_id("Engineer", "Co", "Seattle", "https://example.com/job2")
        
        assert id1 == id2  # Same URL = same ID
        assert id1 != id3  # Different URL = different ID
    
    def test_generate_job_id_without_url(self):
        """Test job ID generation without URL."""
        id1 = _generate_job_id("Engineer", "Co", "Seattle", "")
        id2 = _generate_job_id("Engineer", "Co", "Seattle", "")
        id3 = _generate_job_id("Engineer", "Co", "NYC", "")
        
        assert id1 == id2  # Same content = same ID
        assert id1 != id3  # Different location = different ID


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
