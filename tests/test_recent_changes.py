"""Tests for recent changes across ProfileService and PipelineService."""
import json
from unittest.mock import patch

import pytest

from api.services.profile_service import ProfileService
from api.services.pipeline_service import PipelineService


# ============================================================================
# ProfileService._fill_descriptions_from_text (sequential company matching)
# ============================================================================


class TestFillDescriptionsFromText:
    """Test that description extraction correctly matches roles to raw text."""

    def test_single_role_extraction(self):
        parsed = {
            "experience": [
                {"title": "Senior Engineer", "company": "Acme Corp", "description": ""}
            ]
        }
        raw = """
Senior Engineer
Acme Corp
2020 - 2024
- Built a distributed caching system that reduced latency by 40%
- Led a team of 5 engineers on platform migration
- Architected microservices handling 1M requests per day
"""
        ProfileService._fill_descriptions_from_text(parsed, raw)
        desc = parsed["experience"][0]["description"]
        assert "caching system" in desc
        assert "team of 5" in desc
        assert "microservices" in desc

    def test_two_roles_at_same_company_sequential(self):
        """Duplicate company names should match in order (the BUG-FIX case)."""
        parsed = {
            "experience": [
                {"title": "Senior Engineer", "company": "Cisco", "description": ""},
                {"title": "Staff Engineer", "company": "Cisco", "description": ""},
            ]
        }
        raw = """
Senior Engineer
Cisco
2018 - 2020
- First role achievement about networking protocols
- Second point about TCP stack optimization

Staff Engineer
Cisco
2020 - 2024
- Led observability stack rollout across 100+ services
- Designed tracing infrastructure with OpenTelemetry
"""
        ProfileService._fill_descriptions_from_text(parsed, raw)
        # First role should get the networking content, not observability
        assert "networking protocols" in parsed["experience"][0]["description"]
        assert "observability" not in parsed["experience"][0]["description"]
        # Second role should get the observability content
        assert "observability" in parsed["experience"][1]["description"]
        assert "networking protocols" not in parsed["experience"][1]["description"]

    def test_section_header_terminates_extraction(self):
        """Content after Education header should not leak into last role."""
        parsed = {
            "experience": [
                {"title": "Engineer", "company": "Startup Inc", "description": ""}
            ]
        }
        raw = """
Engineer
Startup Inc
2021 - 2023
- Built the core data pipeline using Kafka and Flink
- Shipped the analytics dashboard for 500+ customers

Education
MS Computer Science, Stanford University
BS Mathematics, MIT
"""
        ProfileService._fill_descriptions_from_text(parsed, raw)
        desc = parsed["experience"][0]["description"]
        assert "data pipeline" in desc
        assert "analytics dashboard" in desc
        assert "Stanford" not in desc
        assert "Computer Science" not in desc

    def test_missing_company_no_crash(self):
        parsed = {
            "experience": [
                {"title": "Engineer", "company": "Not In Resume", "description": ""}
            ]
        }
        raw = "Some other content entirely"
        # Should not raise; description stays empty
        ProfileService._fill_descriptions_from_text(parsed, raw)
        assert parsed["experience"][0]["description"] == ""

    def test_empty_experience_list(self):
        parsed = {"experience": []}
        ProfileService._fill_descriptions_from_text(parsed, "any text")
        assert parsed["experience"] == []


# ============================================================================
# ProfileService._parse_profile_toon (manual nested-array parser)
# ============================================================================


class TestParseProfileToon:
    """Test manual TOON parsing for nested profile data."""

    def test_parses_basic_fields(self):
        toon = """id: test_profile
name: Jane Doe
email: jane@example.com
"""
        result = ProfileService._parse_profile_toon(toon)
        assert result is not None
        assert result["id"] == "test_profile"
        assert result["name"] == "Jane Doe"
        assert result["email"] == "jane@example.com"

    def test_parses_skills_array(self):
        toon = """id: user_x
name: Test
[skills]
  [0]
    name: Python
    level: expert
  [1]
    name: Go
    level: intermediate
"""
        result = ProfileService._parse_profile_toon(toon)
        assert result is not None
        assert len(result["skills"]) == 2
        assert result["skills"][0]["name"] == "Python"
        assert result["skills"][0]["level"] == "expert"
        assert result["skills"][1]["name"] == "Go"
        assert result["skills"][1]["level"] == "intermediate"

    def test_parses_experience_array(self):
        toon = """id: user_y
name: Test User
[experience]
  [0]
    title: Senior Engineer
    company: Acme
    start_date: 2020-01
  [1]
    title: Staff Engineer
    company: Acme
    start_date: 2022-01
"""
        result = ProfileService._parse_profile_toon(toon)
        assert result is not None
        assert len(result["experience"]) == 2
        assert result["experience"][0]["title"] == "Senior Engineer"
        assert result["experience"][1]["title"] == "Staff Engineer"

    def test_returns_none_without_id(self):
        """Profile must have an id field to be considered valid."""
        toon = "name: No ID Here\nemail: x@y.com\n"
        result = ProfileService._parse_profile_toon(toon)
        assert result is None


# ============================================================================
# ProfileService file format migration (JSON preferred, TOON fallback)
# ============================================================================


class TestProfileStorage:
    @pytest.fixture
    def service(self, tmp_path):
        base = tmp_path / "users"
        base.mkdir()
        return ProfileService(base_dir=base)

    def test_save_writes_json_not_toon(self, service):
        service.create_profile(
            user_id="u1", name="Alice", email="alice@example.com",
            phone="", location="Seattle",
        )
        profiles_dir = service._user_profiles_dir("u1")
        json_files = list(profiles_dir.glob("*.json"))
        assert len(json_files) >= 1
        # Verify content is valid JSON
        data = json.loads(json_files[0].read_text())
        assert data["name"] == "Alice"

    def test_load_prefers_json_over_toon(self, service, tmp_path):
        """If both .json and .toon exist, .json wins."""
        profiles_dir = service._user_profiles_dir("u2")

        (profiles_dir / "p.json").write_text(json.dumps({
            "id": "p", "name": "From JSON", "skills": [], "experience": [],
        }))
        (profiles_dir / "p.toon").write_text("id: p\nname: From TOON\n")

        result = service._load_profile("u2", "p")
        assert result is not None
        assert result["name"] == "From JSON"

    def test_load_toon_auto_migrates_to_json(self, service):
        """Loading a TOON-only profile should create a JSON file."""
        profiles_dir = service._user_profiles_dir("u3")
        toon_content = """id: migrated
name: Migrated User
[skills]
  [0]
    name: Python
    level: expert
"""
        (profiles_dir / "migrated.toon").write_text(toon_content)

        result = service._load_profile("u3", "migrated")
        assert result is not None
        assert result["name"] == "Migrated User"
        # JSON file should now exist
        assert (profiles_dir / "migrated.json").exists()

    def test_delete_removes_both_formats(self, service):
        profiles_dir = service._user_profiles_dir("u4")
        (profiles_dir / "p.json").write_text(json.dumps({
            "id": "p", "name": "Test", "skills": [], "experience": [],
        }))
        (profiles_dir / "p.toon").write_text("id: p\nname: Test\n")

        assert service.delete_profile("p", "u4") is True
        assert not (profiles_dir / "p.json").exists()
        assert not (profiles_dir / "p.toon").exists()


# ============================================================================
# PipelineService status reporting (doc_queue / match_queue)
# ============================================================================


class TestPipelineStatus:
    @pytest.fixture
    def service(self):
        """Fresh PipelineService (it's a singleton, reset state)."""
        svc = PipelineService()
        svc._doc_queue = []
        svc._current_doc = None
        svc._last_doc_duration = 0.0
        svc._avg_doc_duration = 0.0
        svc._match_queue = []
        svc._current_match = None
        return svc

    def test_get_status_includes_doc_queue_fields(self, service):
        status = service.get_status()
        assert "doc_queue" in status
        assert status["doc_queue"]["pending"] == 0
        assert status["doc_queue"]["current"] is None
        assert status["doc_queue"]["last_duration_seconds"] == 0.0
        assert status["doc_queue"]["avg_duration_seconds"] == 0.0
        assert status["doc_queue"]["upcoming"] == []

    def test_get_status_includes_match_queue_fields(self, service):
        status = service.get_status()
        assert "match_queue" in status
        assert status["match_queue"]["pending"] == 0
        assert status["match_queue"]["current"] is None
        assert status["match_queue"]["upcoming"] == []

    def test_doc_queue_pending_count(self, service):
        service._doc_queue = [
            {"job_id": "a", "title": "Role A", "company": "Co1", "score": 85},
            {"job_id": "b", "title": "Role B", "company": "Co2", "score": 80},
            {"job_id": "c", "title": "Role C", "company": "Co3", "score": 75},
        ]
        status = service.get_status()
        assert status["doc_queue"]["pending"] == 3
        assert len(status["doc_queue"]["upcoming"]) == 3
        assert status["doc_queue"]["upcoming"][0]["title"] == "Role A"

    def test_current_doc_includes_elapsed_seconds(self, service):
        import time
        service._current_doc = {
            "job_id": "x",
            "title": "Current Role",
            "company": "Current Co",
            "started_at": time.time() - 42,  # 42 seconds ago
        }
        status = service.get_status()
        cur = status["doc_queue"]["current"]
        assert cur is not None
        assert cur["title"] == "Current Role"
        assert cur["company"] == "Current Co"
        # Should be ~42 seconds (allow small variance)
        assert 41 <= cur["elapsed_seconds"] <= 45

    def test_upcoming_limited_to_10(self, service):
        service._doc_queue = [
            {"job_id": f"j{i}", "title": f"Role {i}", "company": f"Co{i}", "score": 70}
            for i in range(25)
        ]
        status = service.get_status()
        # Pending reflects full count
        assert status["doc_queue"]["pending"] == 25
        # Upcoming truncated to 10
        assert len(status["doc_queue"]["upcoming"]) == 10

    def test_match_queue_current_with_elapsed(self, service):
        import time
        service._current_match = {
            "job_id": "m1",
            "title": "ML Engineer",
            "company": "Oura",
            "started_at": time.time() - 10,
        }
        status = service.get_status()
        cur = status["match_queue"]["current"]
        assert cur is not None
        assert cur["title"] == "ML Engineer"
        assert 9 <= cur["elapsed_seconds"] <= 12
