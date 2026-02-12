"""Tests for profile API routes."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime

from api.main import app
from api.models import (
    ProfileResponse, ProfileListItem, Skill, Experience,
    Preferences, Resume, UserResponse,
)


@pytest.fixture
def mock_user():
    return UserResponse(
        id="test-user-123",
        email="test@test.com",
        name="Test User",
        is_admin=False,
        created_at=datetime.now(),
    )


@pytest.fixture
def client(mock_user):
    """Create test client with mocked auth."""
    from api.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def make_profile_response(**overrides):
    defaults = dict(
        id="test_profile",
        name="Test Profile",
        email="test@test.com",
        phone="5551234567",
        location="Seattle, WA",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        skills=[],
        experience=[],
        preferences=Preferences(
            target_roles=[],
            target_locations=[],
            remote_preference="hybrid",
            salary_min=None,
            salary_max=None,
            job_types=["full-time"],
            industries=[],
            excluded_companies=[],
        ),
        resume=Resume(summary="", content="", last_updated=None),
        notes="",
        is_active=True,
    )
    defaults.update(overrides)
    return ProfileResponse(**defaults)


class TestListProfiles:
    @patch("api.routes.profiles.ProfileService")
    def test_list_profiles(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.list_profiles.return_value = [
            ProfileListItem(id="p1", name="Profile 1", location="Seattle", skills_count=3, is_active=True),
            ProfileListItem(id="p2", name="Profile 2", location="Remote", skills_count=1, is_active=False),
        ]

        resp = client.get("/api/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["id"] == "p1"
        assert data[0]["skills_count"] == 3
        assert data[1]["is_active"] is False


class TestCreateProfile:
    @patch("api.routes.profiles.ProfileService")
    def test_create_profile(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.create_profile.return_value = make_profile_response(name="New Profile")

        resp = client.post("/api/profiles", json={
            "name": "New Profile",
            "email": "new@test.com",
            "phone": "5559876543",
            "location": "Portland, OR",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Profile"

    @patch("api.routes.profiles.ProfileService")
    def test_create_profile_minimal(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.create_profile.return_value = make_profile_response(name="Minimal")

        resp = client.post("/api/profiles", json={"name": "Minimal"})
        assert resp.status_code == 201

    @patch("api.routes.profiles.ProfileService")
    def test_create_profile_fails(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.create_profile.return_value = None

        resp = client.post("/api/profiles", json={"name": "Fail"})
        assert resp.status_code == 500

    def test_create_profile_no_name(self, client):
        resp = client.post("/api/profiles", json={})
        assert resp.status_code == 422


class TestGetProfile:
    @patch("api.routes.profiles.ProfileService")
    def test_get_profile(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.get_profile.return_value = make_profile_response()

        resp = client.get("/api/profiles/test_profile")
        assert resp.status_code == 200
        assert resp.json()["id"] == "test_profile"

    @patch("api.routes.profiles.ProfileService")
    def test_get_profile_not_found(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.get_profile.return_value = None

        resp = client.get("/api/profiles/nonexistent")
        assert resp.status_code == 404


class TestUpdateProfile:
    @patch("api.routes.profiles.ProfileService")
    def test_update_basic_fields(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.update_profile.return_value = make_profile_response(name="Updated")

        resp = client.put("/api/profiles/test_profile", json={
            "name": "Updated",
            "email": "updated@test.com",
        })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    @patch("api.routes.profiles.ProfileService")
    def test_update_with_skills(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.update_profile.return_value = make_profile_response(
            skills=[Skill(name="Python", level="advanced", added_at=datetime.now())]
        )

        resp = client.put("/api/profiles/test_profile", json={
            "skills": [{"name": "Python", "level": "advanced"}],
        })
        assert resp.status_code == 200
        assert len(resp.json()["skills"]) == 1

    @patch("api.routes.profiles.ProfileService")
    def test_update_with_preferences(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.update_profile.return_value = make_profile_response()

        resp = client.put("/api/profiles/test_profile", json={
            "preferences": {
                "target_roles": ["SWE", "SRE"],
                "target_locations": ["Seattle"],
                "remote_preference": "remote",
                "salary_min": 150000,
                "salary_max": 250000,
                "job_types": ["full-time"],
                "industries": [],
                "excluded_companies": ["Meta"],
            },
        })
        assert resp.status_code == 200
        mock_svc.update_profile.assert_called_once()

    @patch("api.routes.profiles.ProfileService")
    def test_update_not_found(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.update_profile.return_value = None

        resp = client.put("/api/profiles/nonexistent", json={"name": "X"})
        assert resp.status_code == 404


class TestDeleteProfile:
    @patch("api.routes.profiles.ProfileService")
    def test_delete_profile(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.delete_profile.return_value = True

        resp = client.delete("/api/profiles/test_profile")
        assert resp.status_code == 204

    @patch("api.routes.profiles.ProfileService")
    def test_delete_not_found(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.delete_profile.return_value = False

        resp = client.delete("/api/profiles/nonexistent")
        assert resp.status_code == 404


class TestActivateProfile:
    @patch("api.routes.profiles.ProfileService")
    def test_activate_profile(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.set_active_profile.return_value = make_profile_response(is_active=True)

        resp = client.post("/api/profiles/test_profile/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    @patch("api.routes.profiles.ProfileService")
    def test_activate_not_found(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.set_active_profile.return_value = None

        resp = client.post("/api/profiles/nonexistent/activate")
        assert resp.status_code == 404


class TestImportPdf:
    @patch("api.routes.profiles.ProfileService")
    def test_import_pdf(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.import_from_pdf.return_value = make_profile_response(name="PDF Profile")

        resp = client.post(
            "/api/profiles/import/pdf",
            files={"file": ("resume.pdf", b"fake pdf content", "application/pdf")},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "PDF Profile"

    @patch("api.routes.profiles.ProfileService")
    def test_import_pdf_not_pdf(self, MockService, client):
        resp = client.post(
            "/api/profiles/import/pdf",
            files={"file": ("resume.txt", b"not a pdf", "text/plain")},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    @patch("api.routes.profiles.ProfileService")
    def test_import_pdf_empty(self, MockService, client):
        resp = client.post(
            "/api/profiles/import/pdf",
            files={"file": ("resume.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400

    @patch("api.routes.profiles.ProfileService")
    def test_import_pdf_parse_fails(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.import_from_pdf.return_value = None

        resp = client.post(
            "/api/profiles/import/pdf",
            files={"file": ("resume.pdf", b"fake pdf", "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Ollama" in resp.json()["detail"]


class TestImportLinkedIn:
    @patch("api.routes.profiles.ProfileService")
    def test_import_linkedin(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.import_from_linkedin.return_value = make_profile_response(name="LinkedIn Profile")

        resp = client.post("/api/profiles/import/linkedin", json={
            "url": "https://linkedin.com/in/johndoe"
        })
        assert resp.status_code == 201
        assert resp.json()["name"] == "LinkedIn Profile"

    @patch("api.routes.profiles.ProfileService")
    def test_import_linkedin_invalid_url(self, MockService, client):
        resp = client.post("/api/profiles/import/linkedin", json={
            "url": "https://example.com/profile"
        })
        assert resp.status_code == 400
        assert "LinkedIn" in resp.json()["detail"]

    @patch("api.routes.profiles.ProfileService")
    def test_import_linkedin_fails(self, MockService, client):
        mock_svc = MockService.return_value
        mock_svc.import_from_linkedin.return_value = None

        resp = client.post("/api/profiles/import/linkedin", json={
            "url": "https://linkedin.com/in/johndoe"
        })
        assert resp.status_code == 400
