"""Tests for ProfileService."""
import pytest
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from api.services.profile_service import ProfileService
from api.models import ProfileResponse


@pytest.fixture
def service(tmp_path):
    """Create a ProfileService with an isolated temp directory."""
    base_dir = tmp_path / "users"
    base_dir.mkdir()
    return ProfileService(base_dir=base_dir)


USER_ID = "test-user-123"


class TestCreateProfile:
    def test_create_basic_profile(self, service):
        result = service.create_profile(
            user_id=USER_ID,
            name="John Doe",
            email="john@example.com",
            phone="5551234567",
            location="Seattle, WA"
        )
        assert result is not None
        assert result.name == "John Doe"
        assert result.email == "john@example.com"
        assert result.phone == "5551234567"
        assert result.location == "Seattle, WA"
        assert result.is_active is True  # first profile is active

    def test_create_profile_generates_id(self, service):
        result = service.create_profile(user_id=USER_ID, name="Jane Doe")
        assert result.id == "jane_doe"

    def test_create_duplicate_name_appends_number(self, service):
        r1 = service.create_profile(user_id=USER_ID, name="John Doe")
        r2 = service.create_profile(user_id=USER_ID, name="John Doe")
        assert r1.id == "john_doe"
        assert r2.id == "john_doe_1"

    def test_create_profile_empty_fields_default(self, service):
        result = service.create_profile(user_id=USER_ID, name="Test")
        assert result.email == ""
        assert result.phone == ""
        assert result.location == ""
        assert result.skills == []
        assert result.experience == []
        assert result.notes == ""

    def test_create_profile_initializes_preferences(self, service):
        result = service.create_profile(user_id=USER_ID, name="Test")
        prefs = result.preferences
        assert prefs.target_roles == []
        assert prefs.target_locations == []
        assert prefs.remote_preference == "hybrid"
        assert prefs.salary_min is None
        assert prefs.salary_max is None
        assert prefs.job_types == ["full-time"]
        assert prefs.industries == []
        assert prefs.excluded_companies == []


class TestGetProfile:
    def test_get_existing_profile(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test User")
        fetched = service.get_profile(created.id, USER_ID)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Test User"

    def test_get_nonexistent_profile(self, service):
        result = service.get_profile("nonexistent", USER_ID)
        assert result is None

    def test_get_profile_wrong_user(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test")
        result = service.get_profile(created.id, "other-user")
        assert result is None


class TestListProfiles:
    def test_list_empty(self, service):
        result = service.list_profiles(USER_ID)
        assert result == []

    def test_list_multiple_profiles(self, service):
        service.create_profile(user_id=USER_ID, name="Profile A")
        service.create_profile(user_id=USER_ID, name="Profile B")
        result = service.list_profiles(USER_ID)
        assert len(result) == 2
        names = {p.name for p in result}
        assert names == {"Profile A", "Profile B"}

    def test_list_shows_active_flag(self, service):
        service.create_profile(user_id=USER_ID, name="First")
        service.create_profile(user_id=USER_ID, name="Second")
        result = service.list_profiles(USER_ID)
        active = [p for p in result if p.is_active]
        assert len(active) == 1


class TestUpdateProfile:
    def test_update_basic_fields(self, service):
        created = service.create_profile(user_id=USER_ID, name="Old Name", email="old@test.com")
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            name="New Name",
            email="new@test.com",
            phone="9995551234",
            location="Portland, OR",
            notes="Updated notes"
        )
        assert updated.name == "New Name"
        assert updated.email == "new@test.com"
        assert updated.phone == "9995551234"
        assert updated.location == "Portland, OR"
        assert updated.notes == "Updated notes"

    def test_update_skills_with_dicts(self, service):
        """Test that skills can be passed as dicts (from model_dump)."""
        created = service.create_profile(user_id=USER_ID, name="Test")
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            skills=[
                {"name": "Python", "level": "advanced"},
                {"name": "JavaScript", "level": "intermediate"},
                {"name": "Go", "level": "beginner"},
            ]
        )
        assert len(updated.skills) == 3
        assert updated.skills[0].name == "Python"
        assert updated.skills[0].level == "advanced"
        assert updated.skills[1].name == "JavaScript"
        assert updated.skills[2].name == "Go"
        # added_at should be auto-filled
        for s in updated.skills:
            assert s.added_at is not None

    def test_update_skills_with_empty_list(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test")
        service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            skills=[{"name": "Python", "level": "advanced"}]
        )
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            skills=[]
        )
        assert updated.skills == []

    def test_update_experience_with_dicts(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test")
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            experience=[{
                "title": "Software Engineer",
                "company": "Acme Corp",
                "start_date": "2020-01",
                "end_date": "present",
                "description": "Built things"
            }]
        )
        assert len(updated.experience) == 1
        assert updated.experience[0].title == "Software Engineer"
        assert updated.experience[0].company == "Acme Corp"

    def test_update_preferences_with_dict(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test")
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            preferences={
                "target_roles": ["SWE", "SRE"],
                "target_locations": ["Seattle", "Remote"],
                "remote_preference": "remote",
                "salary_min": 150000,
                "salary_max": 250000,
                "job_types": ["full-time", "contract"],
                "industries": ["tech"],
                "excluded_companies": ["Meta", "Amazon"],
            }
        )
        prefs = updated.preferences
        assert prefs.target_roles == ["SWE", "SRE"]
        assert prefs.target_locations == ["Seattle", "Remote"]
        assert prefs.remote_preference == "remote"
        assert prefs.salary_min == 150000
        assert prefs.salary_max == 250000
        assert prefs.job_types == ["full-time", "contract"]
        assert prefs.industries == ["tech"]
        assert prefs.excluded_companies == ["meta", "amazon"]  # lowercased

    def test_update_resume_with_dict(self, service):
        created = service.create_profile(user_id=USER_ID, name="Test")
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            resume={
                "summary": "Experienced engineer",
                "content": "Full resume text here",
            }
        )
        assert updated.resume.summary == "Experienced engineer"
        assert updated.resume.content == "Full resume text here"
        assert updated.resume.last_updated is not None

    def test_update_nonexistent_profile(self, service):
        result = service.update_profile(
            profile_id="nonexistent",
            user_id=USER_ID,
            name="Test"
        )
        assert result is None

    def test_update_preserves_unmodified_fields(self, service):
        created = service.create_profile(
            user_id=USER_ID,
            name="Original",
            email="original@test.com",
            location="Seattle"
        )
        updated = service.update_profile(
            profile_id=created.id,
            user_id=USER_ID,
            name="Updated"
        )
        assert updated.name == "Updated"
        assert updated.email == "original@test.com"  # preserved
        assert updated.location == "Seattle"  # preserved


class TestDeleteProfile:
    def test_delete_existing_profile(self, service):
        created = service.create_profile(user_id=USER_ID, name="To Delete")
        result = service.delete_profile(created.id, USER_ID)
        assert result is True
        assert service.get_profile(created.id, USER_ID) is None

    def test_delete_nonexistent_profile(self, service):
        result = service.delete_profile("nonexistent", USER_ID)
        assert result is False

    def test_delete_active_profile_switches_active(self, service):
        p1 = service.create_profile(user_id=USER_ID, name="First")
        p2 = service.create_profile(user_id=USER_ID, name="Second")
        # First should be active
        service.delete_profile(p1.id, USER_ID)
        profiles = service.list_profiles(USER_ID)
        assert len(profiles) == 1


class TestSetActiveProfile:
    def test_set_active(self, service):
        p1 = service.create_profile(user_id=USER_ID, name="First")
        p2 = service.create_profile(user_id=USER_ID, name="Second")
        result = service.set_active_profile(p2.id, USER_ID)
        assert result is not None
        assert result.is_active is True

    def test_set_active_nonexistent(self, service):
        result = service.set_active_profile("nonexistent", USER_ID)
        assert result is None


class TestToResponse:
    def test_phone_coerced_to_string(self, service):
        """Phone stored as int in TOON should be coerced to string."""
        created = service.create_profile(user_id=USER_ID, name="Test", phone="5551234567")
        # Manually corrupt the profile to have integer phone (simulating TOON parse)
        profile = service._load_profile(USER_ID, created.id)
        profile["phone"] = 5551234567  # integer
        service._save_profile(USER_ID, profile)

        result = service.get_profile(created.id, USER_ID)
        assert isinstance(result.phone, str)
        assert result.phone == "5551234567"

    def test_missing_fields_default_gracefully(self, service):
        created = service.create_profile(user_id=USER_ID, name="Minimal")
        result = service.get_profile(created.id, USER_ID)
        assert result.email == ""
        assert result.phone == ""
        assert result.location == ""
        assert result.notes == ""
        assert result.skills == []
        assert result.experience == []


class TestImportFromPdf:
    @patch.object(ProfileService, '_parse_resume_with_llm')
    @patch.object(ProfileService, '_extract_text_from_pdf_bytes')
    def test_import_creates_profile(self, mock_extract, mock_parse, service):
        mock_extract.return_value = "John Doe\nSoftware Engineer\nPython, JavaScript"
        mock_parse.return_value = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "5551234567",
            "location": "Seattle, WA",
            "skills": [
                {"name": "Python", "level": "advanced"},
                {"name": "JavaScript", "level": "intermediate"},
            ],
            "experience": [{
                "title": "Software Engineer",
                "company": "TechCo",
                "start_date": "2020-01",
                "end_date": "present",
                "description": "Built web apps"
            }],
            "preferences": {
                "target_roles": ["Software Engineer"],
                "target_locations": ["Seattle"],
                "remote_preference": "hybrid",
            },
            "resume_summary": "Experienced software engineer",
        }

        result = service.import_from_pdf(USER_ID, b"fake pdf bytes")
        assert result is not None
        assert result.name == "John Doe"
        assert result.email == "john@example.com"
        assert len(result.skills) == 2
        assert result.skills[0].name == "Python"
        assert len(result.experience) == 1

    @patch.object(ProfileService, '_extract_text_from_pdf_bytes')
    def test_import_empty_pdf_returns_none(self, mock_extract, service):
        mock_extract.return_value = ""
        result = service.import_from_pdf(USER_ID, b"fake pdf bytes")
        assert result is None

    @patch.object(ProfileService, '_parse_resume_with_llm')
    @patch.object(ProfileService, '_extract_text_from_pdf_bytes')
    def test_import_llm_fails_returns_none(self, mock_extract, mock_parse, service):
        mock_extract.return_value = "Some resume text"
        mock_parse.return_value = None
        result = service.import_from_pdf(USER_ID, b"fake pdf bytes")
        assert result is None
