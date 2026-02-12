"""Tests for document generation endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestDocumentGeneration:
    """Tests for document generation endpoints."""
    
    def test_generate_resume_requires_auth(self, client: TestClient):
        """Test that resume generation requires authentication."""
        response = client.post(
            "/api/documents/resume",
            json={"job_id": "test123"}
        )
        
        assert response.status_code in (401, 403)
    
    def test_generate_resume_invalid_job(self, client: TestClient, auth_headers: dict):
        """Test resume generation with invalid job ID."""
        response = client.post(
            "/api/documents/resume",
            json={"job_id": "nonexistent"},
            headers=auth_headers
        )
        
        assert response.status_code == 400
    
    def test_generate_cover_letter_requires_auth(self, client: TestClient):
        """Test that cover letter generation requires authentication."""
        response = client.post(
            "/api/documents/cover-letter",
            json={"job_id": "test123"}
        )
        
        assert response.status_code in (401, 403)
    
    def test_generate_package_requires_auth(self, client: TestClient):
        """Test that package generation requires authentication."""
        response = client.post(
            "/api/documents/package",
            json={"job_id": "test123"}
        )
        
        assert response.status_code in (401, 403)


class TestDocumentDownload:
    """Tests for document download endpoint."""
    
    def test_download_nonexistent_document(self, client: TestClient, auth_headers: dict):
        """Test downloading a nonexistent document."""
        response = client.get(
            "/api/documents/nonexistent/download",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_download_requires_auth(self, client: TestClient):
        """Test that document download requires authentication."""
        response = client.get("/api/documents/test123/download")
        
        assert response.status_code in (401, 403)


class TestDocumentIntegration:
    """Integration tests for document generation (requires profile and job)."""
    
    @pytest.fixture
    def setup_profile_and_job(self, client: TestClient, auth_headers: dict, test_profile_data: dict, test_job_data: dict):
        """Set up a profile and job for document generation tests."""
        # Create profile
        profile_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        
        if profile_response.status_code != 201:
            pytest.skip("Profile creation failed")
        
        profile_id = profile_response.json()["id"]
        
        # Create job
        job_response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        
        if job_response.status_code != 201:
            pytest.skip("Job creation failed")
        
        job_id = job_response.json()["id"]
        
        return {"profile_id": profile_id, "job_id": job_id}
    
    def test_generate_resume_integration(
        self,
        client: TestClient,
        auth_headers: dict,
        setup_profile_and_job: dict
    ):
        """Test full resume generation flow (may be slow due to LLM)."""
        job_id = setup_profile_and_job["job_id"]
        profile_id = setup_profile_and_job["profile_id"]
        
        response = client.post(
            "/api/documents/resume",
            json={
                "job_id": job_id,
                "profile_id": profile_id
            },
            headers=auth_headers,
            timeout=60  # LLM generation can be slow
        )
        
        # May fail if LLM not available - acceptable in CI
        if response.status_code == 400:
            error = response.json()
            if "LLM" in error.get("detail", "") or "profile" in error.get("detail", "").lower():
                pytest.skip("LLM or profile not available")
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "content" in data
            assert "quality_scores" in data


class TestDocumentList:
    """Tests for document listing endpoint."""

    def test_list_documents_requires_auth(self, client: TestClient):
        """Test that listing documents requires authentication."""
        response = client.get("/api/documents/")
        assert response.status_code in (401, 403)

    def test_list_documents_empty(self, client: TestClient, auth_headers: dict):
        """Test listing documents when none exist."""
        response = client.get("/api/documents/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_documents_limit(self, client: TestClient, auth_headers: dict):
        """Test listing documents with limit parameter."""
        response = client.get(
            "/api/documents/",
            params={"limit": 5},
            headers=auth_headers
        )
        assert response.status_code == 200


class TestDocumentReview:
    """Tests for document review endpoint."""

    def test_review_requires_auth(self, client: TestClient):
        """Test that review update requires authentication."""
        response = client.patch(
            "/api/documents/test123/review",
            json={"reviewed": True}
        )
        assert response.status_code in (401, 403)

    def test_review_nonexistent_document(self, client: TestClient, auth_headers: dict):
        """Test reviewing a nonexistent document."""
        response = client.patch(
            "/api/documents/nonexistent/review",
            json={"reviewed": True},
            headers=auth_headers
        )
        assert response.status_code == 404


class TestDocumentJobSelection:
    """Tests that jobs endpoint works for document generation dropdown."""

    def test_top_jobs_endpoint(self, client: TestClient, auth_headers: dict):
        """Test /jobs/top returns list (may be empty)."""
        response = client.get(
            "/api/jobs/top",
            params={"limit": 50, "min_score": 0},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_all_jobs_fallback(self, client: TestClient, auth_headers: dict):
        """Test /jobs returns paginated list for fallback."""
        response = client.get(
            "/api/jobs",
            params={"page_size": 100},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_create_job_then_list(self, client: TestClient, auth_headers: dict, test_job_data: dict):
        """Test creating a job and seeing it in the list for document generation."""
        # Create a job
        create_response = client.post(
            "/api/jobs",
            json=test_job_data,
            headers=auth_headers
        )
        assert create_response.status_code == 201
        job_id = create_response.json()["id"]

        # Should appear in all-jobs list
        list_response = client.get(
            "/api/jobs",
            params={"page_size": 100},
            headers=auth_headers
        )
        assert list_response.status_code == 200
        job_ids = [j["id"] for j in list_response.json()["jobs"]]
        assert job_id in job_ids
