"""Tests for profile management endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestProfileCRUD:
    """Tests for profile CRUD operations."""
    
    def test_create_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test creating a profile."""
        response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == test_profile_data["name"]
        assert data["email"] == test_profile_data["email"]
        assert data["location"] == test_profile_data["location"]
        assert "id" in data
    
    def test_list_profiles(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test listing profiles."""
        # Create a profile first
        client.post("/api/profiles", json=test_profile_data, headers=auth_headers)
        
        response = client.get("/api/profiles", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_get_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test getting a specific profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Get profile
        response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == profile_id
        assert data["name"] == test_profile_data["name"]
    
    def test_get_nonexistent_profile(self, client: TestClient, auth_headers: dict):
        """Test getting a nonexistent profile returns 404."""
        response = client.get("/api/profiles/nonexistent", headers=auth_headers)
        
        assert response.status_code == 404
    
    def test_update_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating a profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update profile
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"name": "Updated Name", "location": "San Francisco, CA"},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["location"] == "San Francisco, CA"
    
    def test_delete_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test deleting a profile."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "To Delete"},
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Delete profile
        response = client.delete(f"/api/profiles/{profile_id}", headers=auth_headers)
        
        assert response.status_code == 204
        
        # Verify deleted
        get_response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestProfileActivation:
    """Tests for profile activation."""
    
    def test_activate_profile(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test activating a profile."""
        # Create first profile
        create1 = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "Profile 1"},
            headers=auth_headers
        )
        profile1_id = create1.json()["id"]
        
        # Create second profile
        create2 = client.post(
            "/api/profiles",
            json={**test_profile_data, "name": "Profile 2"},
            headers=auth_headers
        )
        profile2_id = create2.json()["id"]
        
        # Activate second profile
        response = client.post(
            f"/api/profiles/{profile2_id}/activate",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] == True


class TestProfileSkillsAndExperience:
    """Tests for profile skills and experience updates."""
    
    def test_update_skills(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating profile skills."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update with skills
        skills = [
            {"name": "Python", "level": "expert"},
            {"name": "JavaScript", "level": "advanced"},
            {"name": "Machine Learning", "level": "intermediate"}
        ]
        
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"skills": skills},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["skills"]) == 3
        assert data["skills"][0]["name"] == "Python"
    
    def test_update_preferences(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test updating profile preferences."""
        # Create profile
        create_response = client.post(
            "/api/profiles",
            json=test_profile_data,
            headers=auth_headers
        )
        profile_id = create_response.json()["id"]
        
        # Update preferences
        preferences = {
            "target_roles": ["Software Engineer", "Backend Developer"],
            "target_locations": ["Seattle", "Remote"],
            "remote_preference": "remote",
            "salary_min": 150000,
            "salary_max": 200000,
            "excluded_companies": ["BadCorp", "WorstCompany"]
        }
        
        response = client.put(
            f"/api/profiles/{profile_id}",
            json={"preferences": preferences},
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["preferences"]["target_roles"] == preferences["target_roles"]
        assert data["preferences"]["salary_min"] == 150000


class TestProfileAuthorization:
    """Tests for profile authorization."""
    
    def test_cannot_access_other_user_profile(self, client: TestClient):
        """Test that users cannot access other users' profiles."""
        # Create first user and profile
        user1_data = {
            "email": "user1@example.com",
            "password": "password123",
            "name": "User One"
        }
        client.post("/api/auth/register", json=user1_data)
        login1 = client.post("/api/auth/login", json={
            "email": user1_data["email"],
            "password": user1_data["password"]
        })
        token1 = login1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Create profile for user 1
        profile_response = client.post(
            "/api/profiles",
            json={"name": "User1 Profile", "location": "Seattle"},
            headers=headers1
        )
        profile_id = profile_response.json()["id"]
        
        # Create second user
        user2_data = {
            "email": "user2@example.com",
            "password": "password123",
            "name": "User Two"
        }
        client.post("/api/auth/register", json=user2_data)
        login2 = client.post("/api/auth/login", json={
            "email": user2_data["email"],
            "password": user2_data["password"]
        })
        token2 = login2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # User 2 should not see user 1's profile
        response = client.get(f"/api/profiles/{profile_id}", headers=headers2)

        # Should return 404 (not found for this user)
        assert response.status_code == 404


class TestPerUserExclusions:
    """Tests that excluded companies are per-user and properly isolated."""

    def test_excluded_companies_stored_per_user(self, client: TestClient):
        """Test that excluded companies are stored per user profile."""
        # Create user A
        user_a = {"email": "user_a@example.com", "password": "password123", "name": "User A"}
        client.post("/api/auth/register", json=user_a)
        login_a = client.post("/api/auth/login", json={"email": user_a["email"], "password": user_a["password"]})
        headers_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        # Create user B
        user_b = {"email": "user_b@example.com", "password": "password123", "name": "User B"}
        client.post("/api/auth/register", json=user_b)
        login_b = client.post("/api/auth/login", json={"email": user_b["email"], "password": user_b["password"]})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # User A sets exclusions
        profile_a = client.post("/api/profiles", json={"name": "A Profile", "location": "Seattle"}, headers=headers_a)
        pa_id = profile_a.json()["id"]
        client.put(f"/api/profiles/{pa_id}", json={
            "preferences": {"excluded_companies": ["Amazon", "Meta"]}
        }, headers=headers_a)

        # User B sets different exclusions
        profile_b = client.post("/api/profiles", json={"name": "B Profile", "location": "NYC"}, headers=headers_b)
        pb_id = profile_b.json()["id"]
        client.put(f"/api/profiles/{pb_id}", json={
            "preferences": {"excluded_companies": ["Google", "Apple"]}
        }, headers=headers_b)

        # Verify user A's exclusions
        resp_a = client.get(f"/api/profiles/{pa_id}", headers=headers_a)
        assert resp_a.status_code == 200
        excl_a = resp_a.json()["preferences"]["excluded_companies"]
        assert "Amazon" in excl_a or "amazon" in excl_a
        assert "Meta" in excl_a or "meta" in excl_a

        # Verify user B's exclusions are different
        resp_b = client.get(f"/api/profiles/{pb_id}", headers=headers_b)
        assert resp_b.status_code == 200
        excl_b = resp_b.json()["preferences"]["excluded_companies"]
        assert "Google" in excl_b or "google" in excl_b
        assert "Apple" in excl_b or "apple" in excl_b

        # User A should not have Google/Apple
        assert "Google" not in excl_a and "google" not in excl_a

    def test_excluded_companies_persist_after_update(self, client: TestClient, auth_headers: dict, test_profile_data: dict):
        """Test that excluded companies persist correctly after profile update."""
        # Create profile
        create = client.post("/api/profiles", json=test_profile_data, headers=auth_headers)
        pid = create.json()["id"]

        # Set exclusions
        client.put(f"/api/profiles/{pid}", json={
            "preferences": {"excluded_companies": ["BadCorp", "WorseInc"]}
        }, headers=auth_headers)

        # Update other fields (name) - exclusions should persist
        client.put(f"/api/profiles/{pid}", json={"name": "New Name"}, headers=auth_headers)

        # Verify exclusions still there
        resp = client.get(f"/api/profiles/{pid}", headers=auth_headers)
        data = resp.json()
        assert data["name"] == "New Name"
        excl = data["preferences"]["excluded_companies"]
        assert len(excl) >= 2
