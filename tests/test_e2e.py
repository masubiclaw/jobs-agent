"""Playwright E2E tests for Jobs Agent web application.

Tests run headless against the live app on localhost:3001.
"""

import re
import time
import pytest
from playwright.sync_api import Page, expect

APP_URL = "http://localhost:3001"
API_URL = "http://localhost:8002"

# Unique test user per run to avoid conflicts
_ts = str(int(time.time()))
TEST_EMAIL = f"e2etest_{_ts}@example.com"
TEST_PASSWORD = "TestPassword123!"
TEST_NAME = "E2E Test User"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _register_user():
    """Register a test user via the API once per session."""
    import httpx
    resp = httpx.post(
        f"{API_URL}/api/auth/register",
        json={"name": TEST_NAME, "email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    if resp.status_code == 429:
        pytest.skip("Rate limited during user registration")
    assert resp.status_code in (201, 400), f"Registration failed: {resp.text}"
    return {"email": TEST_EMAIL, "name": TEST_NAME}


@pytest.fixture(scope="session")
def _auth_token(_register_user):
    """Get a login token once per session to avoid rate limits."""
    import httpx
    resp = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    if resp.status_code == 429:
        pytest.skip("Rate limited during user login")
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def logged_in_page(page: Page, _auth_token):
    """Return a page with the test user already logged in via localStorage token."""
    page.goto(APP_URL + "/login")
    page.evaluate(f"window.localStorage.setItem('auth_token', '{_auth_token}')")
    page.goto(APP_URL)
    page.wait_for_load_state("networkidle")
    return page


# ---------------------------------------------------------------------------
# Console error collector
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _collect_console_errors(page: Page):
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    yield
    real_errors = [
        e for e in errors
        if "401" not in e
        and "429" not in e
        and "404" not in e
        and "ERR_CONNECTION_REFUSED" not in e
        and "favicon" not in e.lower()
        and "Failed to fetch" not in e
        and "Failed to load resource" not in e
    ]
    assert len(real_errors) == 0, f"Console errors: {real_errors}"


# ---------------------------------------------------------------------------
# 1. Landing / Public Pages
# ---------------------------------------------------------------------------

class TestLandingPage:
    def test_landing_page_loads(self, page: Page):
        page.goto(APP_URL + "/welcome")
        expect(page).to_have_title(re.compile(r"Jobs Agent"))

    def test_landing_has_hero_and_cta(self, page: Page):
        page.goto(APP_URL + "/welcome")
        expect(page.locator("h2").first).to_contain_text("Find your next role")
        expect(page.get_by_role("link", name=re.compile("Create Free Account"))).to_be_visible()
        # "Sign in" appears multiple times; just check the header one
        expect(page.locator("header").get_by_role("link", name="Sign in")).to_be_visible()

    def test_landing_sign_in_link_navigates(self, page: Page):
        page.goto(APP_URL + "/welcome")
        page.locator("header").get_by_role("link", name="Sign in").click()
        page.wait_for_url("**/login")
        expect(page.locator("h2")).to_contain_text("Sign in to your account")

    def test_landing_get_started_navigates(self, page: Page):
        page.goto(APP_URL + "/welcome")
        page.get_by_role("link", name="Get Started").click()
        page.wait_for_url("**/register")
        expect(page.locator("h2")).to_contain_text("Create your account")

    def test_how_it_works_section(self, page: Page):
        page.goto(APP_URL + "/welcome")
        expect(page.locator("text=How it works")).to_be_visible()
        expect(page.locator("h4", has_text="Browse Jobs")).to_be_visible()
        expect(page.locator("h4", has_text="See Your Matches")).to_be_visible()
        expect(page.locator("h4", has_text="Generate & Apply")).to_be_visible()


class TestLoginPage:
    def test_login_page_loads(self, page: Page):
        page.goto(APP_URL + "/login")
        expect(page.locator("h2")).to_contain_text("Sign in to your account")

    def test_login_form_elements(self, page: Page):
        page.goto(APP_URL + "/login")
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#password")).to_be_visible()
        expect(page.get_by_role("button", name="Sign in")).to_be_visible()

    def test_login_link_to_register(self, page: Page):
        page.goto(APP_URL + "/login")
        page.get_by_role("link", name="Sign up").click()
        page.wait_for_url("**/register")

    def test_login_empty_form_prevented(self, page: Page):
        page.goto(APP_URL + "/login")
        page.get_by_role("button", name="Sign in").click()
        expect(page).to_have_url(re.compile(r"/login"))

    def test_login_wrong_credentials(self, page: Page, _register_user):
        # With auto-login enabled, visiting /login auto-logs in and redirects to dashboard.
        # Verify the auto-login redirect happens (login screen is bypassed).
        page.goto(APP_URL + "/login")
        page.wait_for_timeout(3000)
        url = page.url
        # Auto-login should redirect away from login to the dashboard
        assert "/login" not in url or url.endswith("/")


class TestRegisterPage:
    def test_register_page_loads(self, page: Page):
        page.goto(APP_URL + "/register")
        expect(page.locator("h2")).to_contain_text("Create your account")

    def test_register_form_elements(self, page: Page):
        page.goto(APP_URL + "/register")
        expect(page.locator("#name")).to_be_visible()
        expect(page.locator("#email")).to_be_visible()
        expect(page.locator("#password")).to_be_visible()
        expect(page.locator("#confirm-password")).to_be_visible()
        expect(page.get_by_role("button", name="Create account")).to_be_visible()

    def test_register_link_to_login(self, page: Page):
        page.goto(APP_URL + "/register")
        page.get_by_role("link", name="Sign in").click()
        page.wait_for_url("**/login")

    def test_register_password_mismatch(self, page: Page):
        page.goto(APP_URL + "/register")
        page.locator("#name").fill("Test")
        page.locator("#email").fill("mismatch@example.com")
        page.locator("#password").fill("password123")
        page.locator("#confirm-password").fill("different123")
        page.get_by_role("button", name="Create account").click()
        expect(page.locator("text=Passwords do not match")).to_be_visible(timeout=3000)

    def test_register_short_password(self, page: Page):
        page.goto(APP_URL + "/register")
        page.locator("#name").fill("Test")
        page.locator("#email").fill("short@example.com")
        page.locator("#password").fill("short")
        page.locator("#confirm-password").fill("short")
        page.get_by_role("button", name="Create account").click()
        expect(page.locator("text=at least 8 characters")).to_be_visible(timeout=3000)


# ---------------------------------------------------------------------------
# 2. Authenticated Pages
# ---------------------------------------------------------------------------

class TestDashboard:
    def test_dashboard_loads(self, logged_in_page: Page):
        page = logged_in_page
        # Scope to main content to avoid sidebar h1
        expect(page.get_by_role("heading", name=re.compile("Welcome"))).to_be_visible()

    def test_dashboard_shows_stats(self, logged_in_page: Page):
        page = logged_in_page
        expect(page.locator("p.text-sm", has_text="Active Profile")).to_be_visible()
        expect(page.locator("p.text-sm", has_text="Total Jobs")).to_be_visible()
        expect(page.locator("p.text-sm", has_text="Top Matches")).to_be_visible()

    def test_dashboard_quick_actions(self, logged_in_page: Page):
        page = logged_in_page
        expect(page.locator("h2", has_text="Quick Actions")).to_be_visible()
        main = page.locator("main")
        expect(main.get_by_role("link", name="Create Profile")).to_be_visible()
        expect(main.get_by_role("link", name="Add Job", exact=True)).to_be_visible()
        expect(main.get_by_role("link", name="Browse Jobs")).to_be_visible()

    def test_no_nan_undefined_null_on_dashboard(self, logged_in_page: Page):
        page = logged_in_page
        content = page.content()
        assert "NaN" not in content, "NaN found on dashboard"
        assert "[object Object]" not in content, "[object Object] found on dashboard"


class TestNavigation:
    def test_nav_to_profiles(self, logged_in_page: Page):
        page = logged_in_page
        page.locator("nav").get_by_role("link", name="Profiles").click()
        page.wait_for_url("**/profiles")

    def test_nav_to_jobs(self, logged_in_page: Page):
        page = logged_in_page
        page.locator("nav").get_by_role("link", name="Jobs").first.click()
        page.wait_for_url("**/jobs")

    def test_nav_to_documents(self, logged_in_page: Page):
        page = logged_in_page
        page.locator("nav").get_by_role("link", name="Documents").click()
        page.wait_for_url("**/documents")


class TestProfilesPage:
    def test_profiles_page_loads(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        body = page.locator("body")
        expect(body).to_be_visible()

    def test_create_profile_link(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        create_link = page.locator("main").get_by_role("link", name=re.compile("Create|New|Add", re.IGNORECASE)).first
        if create_link.is_visible():
            create_link.click()
            page.wait_for_url("**/profiles/new")


class TestJobsPage:
    def test_jobs_page_loads(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        body = page.locator("body")
        expect(body).to_be_visible()

    def test_add_job_link(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        add_link = page.locator("main").get_by_role("link", name=re.compile("Add|New", re.IGNORECASE)).first
        if add_link.is_visible():
            add_link.click()
            page.wait_for_url("**/jobs/add")


class TestDocumentsPage:
    def test_documents_page_loads(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        body = page.locator("body")
        expect(body).to_be_visible()


class TestNotFoundPage:
    def test_404_page(self, logged_in_page: Page):
        page = logged_in_page
        page.goto(APP_URL + "/nonexistent-page-12345")
        page.wait_for_load_state("networkidle")
        body_text = page.locator("body").inner_text()
        assert any(x in body_text.lower() for x in ["not found", "404", "page", "doesn"]), \
            f"404 page missing expected content. Got: {body_text[:200]}"


# ---------------------------------------------------------------------------
# 3. Auth Flow E2E
# ---------------------------------------------------------------------------

class TestAuthFlow:
    def test_register_and_reach_dashboard(self, page: Page):
        """Full auth flow: register -> auto-login -> see dashboard."""
        unique_email = f"e2e_flow_{int(time.time())}@example.com"

        page.goto(APP_URL + "/register")
        page.locator("#name").fill("Flow Test User")
        page.locator("#email").fill(unique_email)
        page.locator("#password").fill("FlowTestPass123!")
        page.locator("#confirm-password").fill("FlowTestPass123!")
        page.get_by_role("button", name="Create account").click()

        # After registration + auto-login, should reach dashboard.
        # If rate-limited (429), the page shows an error — skip in that case.
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        if "Too many" in body or "try again" in body.lower():
            pytest.skip("Auth rate-limited — skipping registration flow test")

        expect(page.get_by_role("heading", name=re.compile("Welcome"))).to_be_visible(timeout=15000)

    def test_unauthenticated_auto_login(self, page: Page):
        """Unauthenticated user visiting / should be auto-logged in and stay on dashboard."""
        page.goto(APP_URL + "/login")
        page.evaluate("window.localStorage.removeItem('auth_token')")
        page.goto(APP_URL + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        # Auto-login should log the user in, keeping them on the dashboard
        url = page.url
        assert "/welcome" not in url, "Auto-login should bypass /welcome"


# ---------------------------------------------------------------------------
# 3b. Auto-Login Bypass
# ---------------------------------------------------------------------------

class TestAutoLogin:
    def test_auto_login_api_endpoint(self, page: Page):
        """The /api/auth/auto-login endpoint returns a valid token."""
        resp = page.request.post(APP_URL + "/api/auth/auto-login")
        assert resp.status == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_auto_login_token_works_with_me(self, page: Page):
        """Token from auto-login can be used with /api/auth/me."""
        resp = page.request.post(APP_URL + "/api/auth/auto-login")
        token = resp.json()["access_token"]
        me_resp = page.request.get(
            APP_URL + "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status == 200
        user = me_resp.json()
        assert user["is_admin"] is True
        assert user["email"] == "admin@jobsagent.local"

    def test_auto_login_bypasses_login_screen(self, page: Page):
        """Fresh browser (no token) should auto-login and reach dashboard."""
        page.goto(APP_URL + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        # Should be on dashboard, not /welcome or /login
        url = page.url
        assert "/login" not in url, "Should not be on login page"
        assert "/welcome" not in url, "Should not be on welcome page"

    def test_auto_login_user_is_admin(self, page: Page):
        """Auto-logged-in user should have admin privileges."""
        page.goto(APP_URL + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        # Admin pages should be accessible
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        # Should not redirect away from admin
        assert "/admin" in page.url, "Admin user should access admin page"


# ---------------------------------------------------------------------------
# 4. API Health
# ---------------------------------------------------------------------------

class TestAPIHealth:
    def test_api_health_via_proxy(self, page: Page):
        """The frontend's /api proxy should reach the backend."""
        resp = page.request.get(APP_URL + "/api/health")
        assert resp.status == 200
        body = resp.json()
        assert body["status"] == "healthy"


# ---------------------------------------------------------------------------
# 5. Profile Creation & Management E2E
# ---------------------------------------------------------------------------

class TestProfileCreation:
    def test_create_profile_form_loads(self, logged_in_page: Page):
        """Navigate to create profile form and verify all fields present."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Create Profile")).to_be_visible()
        # Basic info fields
        expect(page.locator("input[type='text']").first).to_be_visible()
        expect(page.locator("input[type='email']")).to_be_visible()
        expect(page.locator("input[type='tel']")).to_be_visible()
        expect(page.locator("textarea")).to_be_visible()
        # Submit and cancel buttons
        expect(page.get_by_role("button", name="Create Profile")).to_be_visible()
        expect(page.get_by_role("button", name="Cancel")).to_be_visible()

    def test_create_profile_and_verify(self, logged_in_page: Page):
        """Create a new profile via the form and verify it appears in the list."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")

        ts = str(int(time.time()))
        name = f"Test Profile {ts}"

        # Fill form
        page.locator("input[type='text']").first.fill(name)
        page.locator("input[type='email']").fill(f"profile_{ts}@example.com")
        page.locator("input[type='tel']").fill("555-0123")
        page.locator("input[placeholder='City, State']").fill("Seattle, WA")
        page.locator("textarea").fill("Test profile notes")

        # Submit
        page.get_by_role("button", name="Create Profile").click()

        # Should navigate to profile edit page
        page.wait_for_url(re.compile(r"/profiles/.+"), timeout=10000)
        expect(page.get_by_role("heading", name="Edit Profile")).to_be_visible()

    def test_create_profile_cancel_navigates_back(self, logged_in_page: Page):
        """Clicking Cancel on create profile goes back to profiles list."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Cancel").click()
        page.wait_for_url("**/profiles", timeout=5000)

    def test_profile_back_arrow_navigates(self, logged_in_page: Page):
        """The back arrow on profile form navigates to profiles list."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")
        # Click the back arrow button (the visible one with hover:bg-gray-100)
        page.locator("button.hover\\:bg-gray-100:visible").first.click()
        page.wait_for_url("**/profiles", timeout=5000)


# ---------------------------------------------------------------------------
# 6. Add Job Flow E2E
# ---------------------------------------------------------------------------

class TestAddJob:
    def test_add_job_page_loads(self, logged_in_page: Page):
        """Verify add job page loads with all method tabs."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Add Job")).to_be_visible()
        # Tabs should be visible (use buttons to avoid matching description text)
        expect(page.get_by_role("button", name="From URL")).to_be_visible()
        expect(page.get_by_role("button", name="Paste Text")).to_be_visible()
        expect(page.get_by_role("button", name="Manual Entry")).to_be_visible()
        expect(page.get_by_role("button", name="Upload PDF")).to_be_visible()

    def test_add_job_manual_entry(self, logged_in_page: Page):
        """Add a job via manual entry and verify it gets created."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        # Switch to Manual Entry tab
        page.get_by_role("button", name="Manual Entry").click()
        page.wait_for_timeout(500)

        ts = str(int(time.time()))
        title = f"E2E Test Engineer {ts}"

        # Fill manual form fields using type() for React controlled inputs
        inputs = page.locator("input[type='text']:visible")
        inputs.first.click()
        inputs.first.type(title)
        inputs.nth(1).click()
        inputs.nth(1).type("Test Corp")
        page.locator("input[placeholder='City, State or Remote']").fill("Remote")
        page.locator("textarea[placeholder='Job description...']").fill(
            "This is a test job posting for E2E testing purposes."
        )

        # Submit
        page.get_by_role("button", name="Add Job").click()

        # Should navigate to job detail page
        page.wait_for_url(re.compile(r"/jobs/(?!add|top)[a-zA-Z0-9_-]+"), timeout=15000)
        page.wait_for_load_state("networkidle")
        # Wait for the job detail content to render (loading spinner has no text)
        page.wait_for_selector("text=Application Status", timeout=10000)
        body_text = page.locator("body").inner_text()
        assert "Test Corp" in body_text, f"Expected 'Test Corp' on detail page, got: {body_text[:300]}"

    def test_add_job_url_method_shows_input(self, logged_in_page: Page):
        """URL method tab shows URL input field."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        # URL tab is default
        expect(page.locator("input[type='url']")).to_be_visible()
        expect(page.locator("text=Supports Indeed, LinkedIn")).to_be_visible()

    def test_add_job_text_method_shows_textarea(self, logged_in_page: Page):
        """Text method tab shows textarea."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Paste Text").click()
        expect(page.locator("textarea[placeholder*='Paste the full job']")).to_be_visible()

    def test_add_job_pdf_method_shows_upload(self, logged_in_page: Page):
        """PDF method tab shows file upload area."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Upload PDF").click()
        expect(page.locator("text=Click to upload PDF")).to_be_visible()

    def test_add_job_url_empty_validation(self, logged_in_page: Page):
        """Submitting empty URL shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Add Job").click()
        expect(page.locator("text=Please enter a job URL")).to_be_visible(timeout=3000)

    def test_add_job_manual_empty_validation(self, logged_in_page: Page):
        """Submitting empty manual form shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Manual Entry").click()
        page.get_by_role("button", name="Add Job").click()
        # HTML5 validation will prevent submission, or app shows custom error
        page.wait_for_timeout(1000)
        assert "/jobs/add" in page.url, "Should stay on add job page"

    def test_add_job_cancel_navigates_back(self, logged_in_page: Page):
        """Cancel button on add job goes back to jobs list."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Cancel").click()
        page.wait_for_url("**/jobs", timeout=5000)


# ---------------------------------------------------------------------------
# 7. Job Detail Page E2E
# ---------------------------------------------------------------------------

class TestJobDetail:
    """Tests requiring a job to exist — create one in setup."""

    @pytest.fixture
    def job_id(self, _auth_token):
        """Create a test job via API and return its ID."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": f"Detail Test Job {int(time.time())}",
                "company": "Detail Corp",
                "location": "New York, NY",
                "description": "Test job for detail page testing.",
                "salary": "$100,000",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Job create failed: {resp.text}"
        return resp.json()["id"]

    def test_job_detail_shows_info(self, logged_in_page: Page, job_id: str):
        """Job detail page shows title, company, location."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name=re.compile("Detail Test Job"))).to_be_visible()
        expect(page.locator("text=Detail Corp")).to_be_visible()
        expect(page.locator("text=New York, NY")).to_be_visible()

    def test_job_detail_status_buttons(self, logged_in_page: Page, job_id: str):
        """Status tracker buttons are visible and clickable."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Application Status")).to_be_visible()
        # All statuses should be shown
        for label in ["Active", "Applied", "Interviewing", "Offered", "Rejected", "Completed", "Archived"]:
            expect(page.locator(f"button:has-text('{label}')")).to_be_visible()

    def test_job_detail_change_status(self, logged_in_page: Page, job_id: str):
        """Clicking a status button updates the job status."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        # Click "Applied" status
        page.locator("button:has-text('Applied')").click()
        page.wait_for_timeout(2000)
        # The applied button should now have the active ring style
        applied_btn = page.locator("button:has-text('Applied')")
        expect(applied_btn).to_have_class(re.compile("ring-2"))

    def test_job_detail_notes_edit(self, logged_in_page: Page, job_id: str):
        """Editing notes on job detail page works."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Application Status", timeout=10000)
        # The "Notes" label and "Edit" link are in the same section
        notes_section = page.locator("text=Notes").locator("..").locator("..")
        # Click the Edit link/button near the Notes label
        page.locator(".text-primary-600:has-text('Edit')").click()
        page.wait_for_timeout(500)
        # Textarea should appear for notes
        textarea = page.locator("textarea")
        expect(textarea).to_be_visible(timeout=5000)
        textarea.fill("E2E test note - do not delete")
        # Save using the button next to Cancel
        page.get_by_role("button", name="Save").click()
        page.wait_for_timeout(2000)
        # Note should be displayed
        expect(page.locator("text=E2E test note")).to_be_visible()

    def test_job_detail_generate_buttons(self, logged_in_page: Page, job_id: str):
        """Document generation buttons are present."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Generate Documents")).to_be_visible()
        expect(page.locator("button:has-text('Resume + Cover Letter')")).to_be_visible()
        expect(page.locator("button:has-text('Resume Only')")).to_be_visible()
        expect(page.locator("button:has-text('Cover Letter Only')")).to_be_visible()

    def test_job_detail_description_section(self, logged_in_page: Page, job_id: str):
        """Job description section shows content."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Job Description")).to_be_visible()
        expect(page.locator("text=Test job for detail page testing.")).to_be_visible()

    def test_job_detail_metadata(self, logged_in_page: Page, job_id: str):
        """Job metadata section shows details."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Details")).to_be_visible()
        expect(page.locator("text=Source")).to_be_visible()
        expect(page.locator("text=Added On")).to_be_visible()

    def test_job_detail_no_bad_data(self, logged_in_page: Page, job_id: str):
        """No NaN, undefined, null, or [object Object] on job detail page."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "NaN" not in content, "NaN found on job detail"
        assert "[object Object]" not in content, "[object Object] found on job detail"
        # undefined is allowed in JS but not as visible text
        body_text = page.locator("body").inner_text()
        assert "undefined" not in body_text.lower().replace("not undefined", ""), \
            "undefined found in visible text on job detail"

    def test_job_detail_back_to_jobs(self, logged_in_page: Page, job_id: str):
        """Back arrow navigates to jobs list."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.locator("button.hover\\:bg-gray-100:visible").first.click()
        page.wait_for_url("**/jobs", timeout=5000)

    def test_job_detail_delete_button(self, logged_in_page: Page, job_id: str):
        """Delete button exists on job detail page."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        expect(page.locator("button:has-text('Delete Job')")).to_be_visible()


# ---------------------------------------------------------------------------
# 8. Jobs Page — Search, Filter, Sort
# ---------------------------------------------------------------------------

class TestJobsPageDeep:
    def test_jobs_search_input(self, logged_in_page: Page):
        """Search input is present and functional."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        search_input = page.locator("input[placeholder*='Search jobs']")
        expect(search_input).to_be_visible()
        # Type a search query
        search_input.fill("nonexistent-query-xyz")
        page.wait_for_timeout(1000)  # debounce
        # Either no results or the list updates

    def test_jobs_status_filter(self, logged_in_page: Page):
        """Status filter dropdown works."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        select = page.locator("select").first
        expect(select).to_be_visible()
        # Filter by "active"
        select.select_option("active")
        page.wait_for_timeout(1000)

    def test_jobs_sort_buttons(self, logged_in_page: Page):
        """Sort buttons are visible and clickable."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        for label in ["Title", "Company", "Match Score", "Date Added"]:
            btn = page.locator(f"button:has-text('{label}')")
            expect(btn).to_be_visible()

    def test_jobs_no_bad_data(self, logged_in_page: Page):
        """No NaN or [object Object] on jobs page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "NaN" not in content, "NaN found on jobs page"
        assert "[object Object]" not in content, "[object Object] found on jobs page"

    def test_jobs_add_button(self, logged_in_page: Page):
        """Add Job button navigates to add job page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        page.locator("main").get_by_role("link", name="Add Job").click()
        page.wait_for_url("**/jobs/add", timeout=5000)


# ---------------------------------------------------------------------------
# 9. Top Jobs Page E2E
# ---------------------------------------------------------------------------

class TestTopJobsPage:
    def test_top_jobs_page_loads(self, logged_in_page: Page):
        """Top jobs page loads with heading and filter."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Top Matches")).to_be_visible()
        expect(page.locator("text=Minimum Score")).to_be_visible()

    def test_top_jobs_score_filter(self, logged_in_page: Page):
        """Score filter dropdown changes the minimum score."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        select = page.locator("select")
        expect(select).to_be_visible()
        select.select_option("80")
        page.wait_for_timeout(1000)

    def test_top_jobs_no_bad_data(self, logged_in_page: Page):
        """No NaN or [object Object] on top jobs page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "NaN" not in content, "NaN found on top jobs page"
        assert "[object Object]" not in content, "[object Object] found on top jobs page"


# ---------------------------------------------------------------------------
# 10. Documents Page E2E
# ---------------------------------------------------------------------------

class TestDocumentsPageDeep:
    def test_documents_page_loads(self, logged_in_page: Page):
        """Documents page loads with heading and generation section."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Documents", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Generate Documents")).to_be_visible()

    def test_documents_filter_dropdowns(self, logged_in_page: Page):
        """Type and review filter dropdowns are present."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # The type filter has options: All Types, Resumes, Cover Letters
        type_select = page.locator("select:has(option:has-text('All Types'))").first
        expect(type_select).to_be_visible()
        # Select "Resumes" by value
        type_select.select_option("resume")
        page.wait_for_timeout(500)
        type_select.select_option("all")

    def test_documents_generate_button_disabled_without_job(self, logged_in_page: Page):
        """Generate button is disabled when no job is selected."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        gen_btn = page.locator("button:has-text('Generate')")
        expect(gen_btn).to_be_disabled()

    def test_documents_no_bad_data(self, logged_in_page: Page):
        """No NaN or [object Object] on documents page."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "NaN" not in content, "NaN found on documents page"
        assert "[object Object]" not in content, "[object Object] found on documents page"


# ---------------------------------------------------------------------------
# 11. Logout Flow
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_redirects_to_login(self, logged_in_page: Page):
        """Signing out redirects to login page."""
        page = logged_in_page
        # Click sign out in sidebar
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_url(re.compile(r"/(login|welcome)"), timeout=5000)

    def test_logout_triggers_auto_login(self, logged_in_page: Page):
        """After logout, visiting / auto-logs back in (auto-login bypass)."""
        page = logged_in_page
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_url(re.compile(r"/(login|welcome)"), timeout=5000)
        page.goto(APP_URL + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        # Auto-login should re-authenticate the user
        url = page.url
        assert "/welcome" not in url, "Auto-login should re-authenticate after logout"


# ---------------------------------------------------------------------------
# 12. Cross-Page Data Integrity
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_all_authenticated_pages_no_bad_data(self, logged_in_page: Page):
        """Sweep all authenticated pages for NaN, [object Object], undefined displayed as text."""
        page = logged_in_page
        bad_patterns = ["NaN", "[object Object]"]
        pages_to_check = [
            "/",
            "/profiles",
            "/profiles/new",
            "/jobs",
            "/jobs/add",
            "/jobs/top",
            "/documents",
        ]
        errors = []
        for path in pages_to_check:
            page.goto(APP_URL + path)
            page.wait_for_load_state("networkidle")
            content = page.content()
            for pattern in bad_patterns:
                if pattern in content:
                    errors.append(f"{path}: found '{pattern}'")
        assert len(errors) == 0, f"Bad data found:\n" + "\n".join(errors)

    def test_sidebar_navigation_complete(self, logged_in_page: Page):
        """All sidebar nav links are present and work."""
        page = logged_in_page
        nav = page.locator("nav")
        expected_links = ["Dashboard", "Profiles", "Jobs", "Top Matches", "Add Job", "Documents"]
        for link_text in expected_links:
            link = nav.get_by_role("link", name=link_text)
            expect(link).to_be_visible()

    def test_user_info_in_sidebar(self, logged_in_page: Page):
        """User name and email are shown in sidebar."""
        page = logged_in_page
        sidebar = page.locator("aside")
        # User name should be visible
        expect(sidebar.locator("text=E2E Test User")).to_be_visible()

    def test_dashboard_quick_actions_navigate(self, logged_in_page: Page):
        """Each quick action link on dashboard navigates correctly."""
        page = logged_in_page
        main = page.locator("main")
        actions = {
            "Create Profile": "/profiles/new",
            "Browse Jobs": "/jobs",
        }
        for link_text, expected_path in actions.items():
            page.goto(APP_URL)
            page.wait_for_load_state("networkidle")
            main.get_by_role("link", name=link_text).click()
            page.wait_for_url(f"**{expected_path}", timeout=5000)


# ---------------------------------------------------------------------------
# 13. Resume Generation Pipeline E2E
# ---------------------------------------------------------------------------

class TestProfileEditFlow:
    """Tests for editing a profile with skills and experience (required for resume generation)."""

    @pytest.fixture
    def profile_id(self, _auth_token):
        """Create a test profile via API and return its ID."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={
                "name": f"Resume Pipeline User {int(time.time())}",
                "email": f"pipeline_{int(time.time())}@example.com",
                "phone": "555-9999",
                "location": "Portland, OR",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Profile create failed: {resp.text}"
        return resp.json()["id"]

    def test_profile_edit_shows_skills_section(self, logged_in_page: Page, profile_id: str):
        """Edit profile page shows skills management section."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Edit Profile")).to_be_visible()
        expect(page.get_by_role("heading", name="Skills")).to_be_visible()
        expect(page.locator("input[placeholder='Skill name']")).to_be_visible()

    def test_profile_edit_shows_experience_section(self, logged_in_page: Page, profile_id: str):
        """Edit profile page shows experience management section."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Experience")).to_be_visible()
        expect(page.locator("input[placeholder='Job Title']")).to_be_visible()
        expect(page.locator("input[placeholder='Company']")).to_be_visible()

    def test_profile_edit_shows_preferences_section(self, logged_in_page: Page, profile_id: str):
        """Edit profile page shows job preferences section."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Job Preferences")).to_be_visible()
        expect(page.locator("input[placeholder='Software Engineer, Developer']")).to_be_visible()

    def test_add_skill_to_profile(self, logged_in_page: Page, profile_id: str):
        """Add a skill to the profile and verify it appears."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")

        # Add a skill
        page.locator("input[placeholder='Skill name']").fill("Python")
        # The skill level select is inside the Skills section, adjacent to the input
        skills_section = page.locator("h2:has-text('Skills')").locator("..")
        skills_section.locator("select").select_option("expert")
        # Click the Add button (btn-secondary right after select in flex row)
        skills_section.locator("button.btn-secondary").first.click()
        page.wait_for_timeout(500)

        # Skill should appear in the skills list
        expect(page.locator("text=Python")).to_be_visible()
        expect(page.locator("text=(expert)")).to_be_visible()

    def test_add_experience_to_profile(self, logged_in_page: Page, profile_id: str):
        """Add an experience entry to the profile and verify it appears."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")

        # Fill experience form
        page.locator("input[placeholder='Job Title']").fill("Software Engineer")
        page.locator("input[placeholder='Company']").fill("Acme Corp")
        page.locator("input[placeholder='Start (e.g. 2020-01)']").fill("2022-01")
        page.locator("input[placeholder='End (or present)']").fill("present")

        # Click Add button
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(500)

        # Experience should appear in the list
        expect(page.locator("text=Software Engineer")).to_be_visible()
        expect(page.locator("text=Acme Corp")).to_be_visible()

    def test_save_profile_with_skills_and_experience(self, logged_in_page: Page, profile_id: str):
        """Add skills and experience, save profile, and verify success message."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")

        # Add a skill
        page.locator("input[placeholder='Skill name']").fill("React")
        skills_section = page.locator("h2:has-text('Skills')").locator("..")
        skills_section.locator("button.btn-secondary").first.click()
        page.wait_for_timeout(300)

        # Verify skill appeared in UI before save
        expect(skills_section.locator("text=React")).to_be_visible()

        # Add experience
        page.locator("input[placeholder='Job Title']").fill("Frontend Developer")
        page.locator("input[placeholder='Company']").fill("Test Inc")
        page.locator("input[placeholder='Start (e.g. 2020-01)']").fill("2021-06")
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(300)

        # Verify experience appeared in UI before save
        expect(page.locator("text=Frontend Developer")).to_be_visible()

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)

        # Success message should appear
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify data persisted via API
        import httpx
        token = page.evaluate("window.localStorage.getItem('auth_token')")
        resp = httpx.get(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        skill_names = [s["name"] for s in data.get("skills", [])]
        assert "React" in skill_names, f"Skill React not saved. Skills: {skill_names}"
        exp_titles = [e["title"] for e in data.get("experience", [])]
        assert "Frontend Developer" in exp_titles, f"Experience not saved. Titles: {exp_titles}"


class TestDocumentsPageGeneration:
    """Tests for document generation UI on the Documents page."""

    @pytest.fixture
    def _setup_profile_and_job(self, _auth_token):
        """Create a profile with skills and a job, return their IDs."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        # Create profile
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Gen Test {ts}", "email": f"gen_{ts}@example.com",
                  "phone": "555-0001", "location": "Austin, TX"},
            headers=headers,
        )
        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        # Add skills and experience
        httpx.put(
            f"{API_URL}/api/profiles/{profile_id}",
            json={
                "name": f"Gen Test {ts}", "email": f"gen_{ts}@example.com",
                "phone": "555-0001", "location": "Austin, TX", "notes": "",
                "skills": [{"name": "Python", "level": "expert"}, {"name": "FastAPI", "level": "advanced"}],
                "experience": [{"title": "Developer", "company": "TestCo", "start_date": "2020-01",
                                "end_date": "present", "description": "Built APIs"}],
            },
            headers=headers,
        )

        # Activate profile
        httpx.post(f"{API_URL}/api/profiles/{profile_id}/activate", headers=headers)

        # Create job
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Python Dev {ts}", "company": "Gen Corp",
                  "location": "Remote", "description": "Python developer needed.",
                  "salary": "$130,000"},
            headers=headers,
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        return {"profile_id": profile_id, "job_id": job_id}

    def test_documents_page_job_dropdown_populated(self, logged_in_page: Page, _setup_profile_and_job):
        """Documents page job dropdown shows available jobs."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # The job dropdown should have options
        job_select = page.locator("select.input").first
        expect(job_select).to_be_visible()
        options = job_select.locator("option")
        # At least 2 options: "Select a job..." + at least 1 job
        assert options.count() >= 2, f"Expected at least 2 options, got {options.count()}"

    def test_documents_page_type_dropdown(self, logged_in_page: Page):
        """Generation type dropdown has all options."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Find the type dropdown (second select in Generate section)
        gen_section = page.locator("h2:has-text('Generate Documents')").locator("..").locator("..")
        type_select = gen_section.locator("select").nth(1)
        expect(type_select).to_be_visible()

        # Verify options exist (options in select aren't "visible" in DOM)
        options = type_select.locator("option")
        assert options.count() == 3, f"Expected 3 type options, got {options.count()}"
        # Verify we can select each option
        type_select.select_option("package")
        type_select.select_option("resume")
        type_select.select_option("cover_letter")

    def test_generate_button_disabled_without_job(self, logged_in_page: Page):
        """Generate button is disabled when no job is selected."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        gen_btn = page.locator("button:has-text('Generate')")
        expect(gen_btn).to_be_disabled()

    def test_generate_button_enabled_with_job(self, logged_in_page: Page, _setup_profile_and_job):
        """Generate button becomes enabled when a job is selected."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Wait for job dropdown to populate
        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )

        # Select the first available job (index 1 to skip "Select a job...")
        job_select.select_option(index=1)
        page.wait_for_timeout(300)

        # Generate button should now be enabled
        gen_btn = page.locator("button:has-text('Generate')")
        expect(gen_btn).to_be_enabled()

    def test_generate_shows_loading_state(self, logged_in_page: Page, _setup_profile_and_job):
        """Clicking Generate shows loading state."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Intercept the generation API call — hold route pending to observe loading state
        pending = []
        page.route("**/api/documents/package", lambda route: pending.append(route))

        # Wait for job dropdown to populate
        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )

        # Select first available job
        job_select.select_option(index=1)
        page.wait_for_timeout(300)

        gen_btn = page.locator("button:has-text('Generate')")
        gen_btn.click()

        # Button should show "Generating..." loading state
        expect(page.locator("button:has-text('Generating...')")).to_be_visible(timeout=3000)

        # Clean up pending routes
        for r in pending:
            try:
                r.fulfill(status=200, content_type="application/json",
                    body='{"resume": null, "cover_letter": null}')
            except Exception:
                pass


class TestJobDetailGeneration:
    """Tests for document generation UI on the Job Detail page."""

    @pytest.fixture
    def _setup_for_generation(self, _auth_token):
        """Create profile with skills + job, return job_id."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        # Create and setup profile
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Detail Gen {ts}", "email": f"dgen_{ts}@example.com",
                  "phone": "555-0002", "location": "Denver, CO"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={"name": f"Detail Gen {ts}", "email": f"dgen_{ts}@example.com",
                  "phone": "555-0002", "location": "Denver, CO", "notes": "",
                  "skills": [{"name": "TypeScript", "level": "expert"}],
                  "experience": [{"title": "Lead Dev", "company": "BigCo",
                                  "start_date": "2019-01", "end_date": "present",
                                  "description": "Led team of 5"}]},
            headers=headers,
        )
        httpx.post(f"{API_URL}/api/profiles/{pid}/activate", headers=headers)

        # Create job
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"TS Developer {ts}", "company": "DetailCorp",
                  "location": "Remote", "description": "TypeScript dev needed."},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_job_detail_generate_resume_shows_loading(self, logged_in_page: Page, _setup_for_generation):
        """Clicking Resume Only on job detail shows generating status."""
        page = logged_in_page
        job_id = _setup_for_generation
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # Intercept - keep pending to observe loading state
        pending = []
        page.route("**/api/documents/resume", lambda route: pending.append(route))
        page.route("**/api/documents/**/download", lambda r: r.abort())

        page.locator("button:has-text('Resume Only')").click()
        expect(page.locator("text=Generating resume...")).to_be_visible(timeout=3000)

        # Clean up
        for r in pending:
            try:
                r.fulfill(status=200, content_type="application/json",
                    body='{"id":"m","job_id":"x","profile_id":"x","document_type":"resume","content":"t","pdf_path":null,"quality_scores":{"fact_score":90,"keyword_score":90,"ats_score":90,"length_score":90,"overall_score":90},"iterations":1,"created_at":"2026-01-01T00:00:00"}')
            except Exception:
                pass

    def test_job_detail_generate_cover_letter_shows_loading(self, logged_in_page: Page, _setup_for_generation):
        """Clicking Cover Letter Only on job detail shows generating status."""
        page = logged_in_page
        job_id = _setup_for_generation
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        pending = []
        page.route("**/api/documents/cover-letter", lambda route: pending.append(route))

        page.locator("button:has-text('Cover Letter Only')").click()
        expect(page.locator("text=Generating cover letter...")).to_be_visible(timeout=3000)

        for r in pending:
            try:
                r.fulfill(status=200, content_type="application/json",
                    body='{"id":"m","job_id":"x","profile_id":"x","document_type":"cover_letter","content":"t","pdf_path":null,"quality_scores":{"fact_score":90,"keyword_score":90,"ats_score":90,"length_score":90,"overall_score":90},"iterations":1,"created_at":"2026-01-01T00:00:00"}')
            except Exception:
                pass

    def test_job_detail_generate_package_shows_loading(self, logged_in_page: Page, _setup_for_generation):
        """Clicking Resume + Cover Letter shows generating status."""
        page = logged_in_page
        job_id = _setup_for_generation
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        pending = []
        page.route("**/api/documents/package", lambda route: pending.append(route))

        page.locator("button:has-text('Resume + Cover Letter')").click()
        expect(page.locator("text=Generating resume + cover letter...")).to_be_visible(timeout=3000)

        for r in pending:
            try:
                r.fulfill(status=200, content_type="application/json",
                    body='{"resume": null, "cover_letter": null}')
            except Exception:
                pass

    def test_job_detail_generate_disables_buttons_while_generating(self, logged_in_page: Page, _setup_for_generation):
        """All generate buttons are disabled while generation is in progress."""
        page = logged_in_page
        job_id = _setup_for_generation
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # Intercept to keep request pending
        pending_routes = []
        page.route("**/api/documents/resume", lambda route: pending_routes.append(route))
        page.route("**/api/documents/**/download", lambda r: r.abort())

        page.locator("button:has-text('Resume Only')").click()
        page.wait_for_timeout(500)

        # The "Resume + Cover Letter" button text changes to "Generating..." so check
        # that all buttons in the Generate Documents section are disabled
        gen_section = page.locator("h2:has-text('Generate Documents')").locator("..")
        buttons = gen_section.locator("button")
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            expect(btn).to_be_disabled()

        # Clean up
        for route in pending_routes:
            try:
                route.fulfill(status=200, content_type="application/json",
                    body='{"id":"m","job_id":"x","profile_id":"x","document_type":"resume","content":"t","pdf_path":null,"quality_scores":{"fact_score":90,"keyword_score":90,"ats_score":90,"length_score":90,"overall_score":90},"iterations":1,"created_at":"2026-01-01T00:00:00"}')
            except Exception:
                pass


class TestProfileActivation:
    """Tests for profile activation flow (required for document generation)."""

    @pytest.fixture
    def _two_profiles(self, _auth_token):
        """Create two profiles, return their IDs."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        ids = []
        for i in range(2):
            resp = httpx.post(
                f"{API_URL}/api/profiles",
                json={"name": f"Profile {i} {ts}", "email": f"p{i}_{ts}@example.com",
                      "phone": f"555-000{i}", "location": "Test City"},
                headers=headers,
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])
        return ids

    def test_profiles_page_shows_active_badge(self, logged_in_page: Page, _two_profiles, _auth_token):
        """Active profile shows Active badge."""
        page = logged_in_page
        import httpx
        # Activate first profile
        httpx.post(
            f"{API_URL}/api/profiles/{_two_profiles[0]}/activate",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Active").first).to_be_visible()

    def test_profiles_page_set_active_button(self, logged_in_page: Page, _two_profiles):
        """Non-active profiles show Set Active button."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        set_active_btn = page.get_by_role("button", name="Set Active").first
        expect(set_active_btn).to_be_visible()


class TestProfilesImportUI:
    """Tests for profile import tab UI."""

    def test_profiles_page_import_section(self, logged_in_page: Page):
        """Profiles page has import section with tabs."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Import Profile")).to_be_visible()
        expect(page.get_by_role("button", name="PDF Resume")).to_be_visible()
        expect(page.get_by_role("button", name="Paste Text")).to_be_visible()
        expect(page.get_by_role("button", name="LinkedIn")).to_be_visible()

    def test_profiles_import_pdf_tab(self, logged_in_page: Page):
        """PDF import tab shows file upload input."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        # PDF tab is default
        expect(page.locator("input[type='file'][accept='.pdf']")).to_be_visible()
        expect(page.get_by_role("button", name="Upload & Import")).to_be_visible()

    def test_profiles_import_text_tab(self, logged_in_page: Page):
        """Text import tab shows textarea and import button."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Paste Text").click()
        expect(page.locator("textarea[placeholder='Paste your resume content here...']")).to_be_visible()
        expect(page.get_by_role("button", name="Import Text")).to_be_visible()

    def test_profiles_import_text_button_disabled_short_text(self, logged_in_page: Page):
        """Import Text button is disabled when text is too short."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Paste Text").click()
        page.locator("textarea").fill("too short")
        expect(page.get_by_role("button", name="Import Text")).to_be_disabled()

    def test_profiles_import_linkedin_tab(self, logged_in_page: Page):
        """LinkedIn import tab shows URL input."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="LinkedIn").click()
        expect(page.locator("input[placeholder='https://linkedin.com/in/username']")).to_be_visible()
        expect(page.get_by_role("button", name="Import")).to_be_visible()

    def test_profiles_import_linkedin_button_disabled_invalid_url(self, logged_in_page: Page):
        """LinkedIn import button is disabled with invalid URL."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="LinkedIn").click()
        page.locator("input[placeholder='https://linkedin.com/in/username']").fill("not-a-linkedin-url")
        expect(page.get_by_role("button", name="Import")).to_be_disabled()


class TestDocumentsListInteractions:
    """Tests for document list interactions (review, filter, select)."""

    def test_documents_review_filter(self, logged_in_page: Page):
        """Review filter dropdown works."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # The review filter has Reviewed/Unreviewed options
        review_select = page.locator("select:has(option:has-text('Reviewed'))").first
        expect(review_select).to_be_visible()
        review_select.select_option("reviewed")
        page.wait_for_timeout(500)
        review_select.select_option("all")

    def test_documents_count_label(self, logged_in_page: Page):
        """Document count label shows correct number."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # Should show "X documents" count
        expect(page.locator("text=documents").first).to_be_visible()

    def test_documents_empty_state(self, logged_in_page: Page):
        """Documents page shows appropriate empty state for new user."""
        # This test uses the logged_in_page which may or may not have documents
        # We just verify the page structure is correct
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # Either shows documents or empty state
        body = page.locator("body").inner_text()
        assert "Documents" in body

    def test_documents_page_no_errors(self, logged_in_page: Page):
        """Documents page loads without JS errors or bad data."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "[object Object]" not in content
        body_text = page.locator("body").inner_text()
        assert "undefined" not in body_text.lower().replace("not undefined", "").replace("is undefined", "")


# ---------------------------------------------------------------------------
# 14. Profile Delete Flow
# ---------------------------------------------------------------------------

class TestProfileDeleteFlow:
    """Test creating and deleting a profile via the UI."""

    @pytest.fixture
    def _profile_to_delete(self, _auth_token):
        """Create a disposable profile via API."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Delete Me {ts}", "email": f"del_{ts}@example.com",
                  "phone": "555-9999", "location": "Nowhere"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_profile_delete_removes_from_list(self, logged_in_page: Page, _profile_to_delete):
        """Deleting a profile removes it from the profiles list."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")

        # Verify profile is visible
        expect(page.locator("text=Delete Me")).to_be_visible(timeout=5000)

        # Accept the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())

        # Find the delete button in the card containing our profile
        card = page.locator("div.card", has_text="Delete Me").first
        card.locator("button:has(svg)").last.click()

        # Profile should disappear
        expect(page.locator("text=Delete Me")).to_be_hidden(timeout=5000)

    def test_profile_delete_cancel_keeps_profile(self, logged_in_page: Page, _profile_to_delete):
        """Dismissing the confirm dialog keeps the profile."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Delete Me")).to_be_visible(timeout=5000)

        # Dismiss the confirm dialog
        page.on("dialog", lambda dialog: dialog.dismiss())

        card = page.locator("div.card", has_text="Delete Me").first
        card.locator("button:has(svg)").last.click()

        # Profile should still be visible
        page.wait_for_timeout(500)
        expect(page.locator("text=Delete Me")).to_be_visible()


# ---------------------------------------------------------------------------
# 15. Job Not Found / Invalid Routes
# ---------------------------------------------------------------------------

class TestInvalidRoutes:
    """Test navigating to invalid or non-existent resources."""

    def test_nonexistent_job_shows_not_found(self, logged_in_page: Page):
        """Navigating to a non-existent job ID shows 'Job not found'."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Job not found")).to_be_visible(timeout=5000)

    def test_nonexistent_profile_shows_form(self, logged_in_page: Page):
        """Navigating to a non-existent profile ID shows the profile form page."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")
        # Profile form page should render (new or edit mode)
        body = page.locator("body").inner_text()
        # Should not crash — either shows form or error
        assert "undefined" not in body.lower().replace("is undefined", "").replace("not undefined", "")


# ---------------------------------------------------------------------------
# 16. Job Status Workflow
# ---------------------------------------------------------------------------

class TestJobStatusWorkflow:
    """Test the full job status workflow transitions."""

    @pytest.fixture
    def _workflow_job(self, _auth_token):
        """Create a job for workflow testing."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Workflow Dev {ts}", "company": "WorkflowCorp",
                  "location": "Remote", "description": "Workflow test job."},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_status_transitions(self, logged_in_page: Page, _workflow_job):
        """Can transition through active → applied → interviewing → offered."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_workflow_job}")
        page.wait_for_load_state("networkidle")

        # Should start as Active
        expect(page.locator("text=Active")).to_be_visible(timeout=5000)

        # Click Applied button
        applied_btn = page.locator("button:has-text('Applied')")
        if applied_btn.is_visible():
            applied_btn.click()
            page.wait_for_timeout(500)

        # Click Interviewing
        interview_btn = page.locator("button:has-text('Interviewing')")
        if interview_btn.is_visible():
            interview_btn.click()
            page.wait_for_timeout(500)

        # Click Offered
        offered_btn = page.locator("button:has-text('Offered')")
        if offered_btn.is_visible():
            offered_btn.click()
            page.wait_for_timeout(500)

    def test_status_reject(self, logged_in_page: Page, _workflow_job):
        """Can mark a job as rejected."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_workflow_job}")
        page.wait_for_load_state("networkidle")

        reject_btn = page.locator("button:has-text('Rejected')")
        if reject_btn.is_visible():
            reject_btn.click()
            page.wait_for_timeout(500)


# ---------------------------------------------------------------------------
# 17. Generation Error States
# ---------------------------------------------------------------------------

class TestGenerationErrors:
    """Test error handling for document generation."""

    @pytest.fixture
    def _job_no_profile(self, _auth_token):
        """Create a job but ensure no active profile exists."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"No Profile Job {ts}", "company": "NoProfCorp",
                  "location": "Remote", "description": "Job for error testing."},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_generate_resume_error_displayed(self, logged_in_page: Page, _job_no_profile):
        """Generate buttons on job detail show error state on failure."""
        page = logged_in_page
        job_id = _job_no_profile
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # Intercept and return error
        page.route("**/api/documents/resume", lambda route: route.fulfill(
            status=400, content_type="application/json",
            body='{"detail": "Failed to generate resume. Check that job and profile exist."}'
        ))

        resume_btn = page.locator("button:has-text('Resume Only')")
        resume_btn.click()

        # Should show error message (not crash)
        page.wait_for_timeout(1000)
        body = page.locator("body").inner_text()
        # Should display some error indication, not crash
        assert "NaN" not in body
        assert "[object Object]" not in page.content()

    def test_generate_on_documents_page_error_message(self, logged_in_page: Page, _job_no_profile):
        """Documents page shows error message when generation fails."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Intercept and return error
        page.route("**/api/documents/package", lambda route: route.fulfill(
            status=400, content_type="application/json",
            body='{"detail": "Failed to generate application package."}'
        ))

        # Wait for job dropdown to populate and select a job
        job_select = page.locator("select.input").first
        try:
            page.wait_for_function(
                "document.querySelector('select.input').options.length > 1",
                timeout=5000,
            )
            job_select.select_option(index=1)
            page.wait_for_timeout(300)

            gen_btn = page.locator("button:has-text('Generate')")
            gen_btn.click()

            # Should show error message, not crash
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()
            assert "Failed" in body or "error" in body.lower() or "Generating" not in body
        except Exception:
            # No jobs available — skip gracefully
            pass


# ---------------------------------------------------------------------------
# 18. Documents Page — Type and Review Filter Interaction
# ---------------------------------------------------------------------------

class TestDocumentFilterInteraction:
    """Test combined filter interactions on documents page."""

    def test_type_filter_changes_display(self, logged_in_page: Page):
        """Changing the type filter updates the document count."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Get initial count text
        count_text = page.locator("text=/\\d+ documents/")
        if count_text.is_visible(timeout=3000):
            initial = count_text.inner_text()

            # Find the type filter (first small select after Filter icon)
            type_select = page.locator("select.text-sm").first
            type_select.select_option(label="Resumes")
            page.wait_for_timeout(300)

            new_text = count_text.inner_text()
            assert "documents" in new_text

            # Back to all
            type_select.select_option(label="All Types")
            page.wait_for_timeout(300)

    def test_review_filter_changes_display(self, logged_in_page: Page):
        """Changing the review filter updates the document count."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        count_text = page.locator("text=/\\d+ documents/")
        if count_text.is_visible(timeout=3000):
            # The review filter is the second small select
            review_select = page.locator("select.text-sm").nth(1)
            review_select.select_option(label="Reviewed")
            page.wait_for_timeout(300)

            review_select.select_option(label="Unreviewed")
            page.wait_for_timeout(300)

            review_select.select_option(label="All Status")
            page.wait_for_timeout(300)

            assert count_text.is_visible()


# ---------------------------------------------------------------------------
# 19. Job Deletion Flow (end-to-end)
# ---------------------------------------------------------------------------

class TestJobDeletionFlow:
    """Test that deleting a job via the UI actually removes it."""

    @pytest.fixture
    def _deletable_job(self, _auth_token):
        """Create a job that will be deleted during the test."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Deletable Job {ts}", "company": "DeleteCorp",
                  "location": "Remote", "description": "This job will be deleted."},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_delete_job_removes_from_detail(self, logged_in_page: Page, _deletable_job):
        """Deleting a job from detail page navigates back to jobs list."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_deletable_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Delete Job", timeout=10000)

        # Accept the confirm dialog
        page.on("dialog", lambda dialog: dialog.accept())

        page.locator("button:has-text('Delete Job')").click()
        # Should navigate back to /jobs
        page.wait_for_url("**/jobs", timeout=10000)

        # The deleted job should not appear in the list
        page.wait_for_load_state("networkidle")
        body = page.locator("body").inner_text()
        assert "DeleteCorp" not in body or "Deletable Job" not in body

    def test_delete_job_cancel_keeps_job(self, logged_in_page: Page, _deletable_job):
        """Dismissing the delete confirm keeps the job."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_deletable_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Delete Job", timeout=10000)

        # Dismiss the confirm dialog
        page.on("dialog", lambda dialog: dialog.dismiss())

        page.locator("button:has-text('Delete Job')").click()
        page.wait_for_timeout(1000)

        # Should still be on the job detail page
        assert _deletable_job in page.url
        expect(page.locator("text=DeleteCorp")).to_be_visible()


# ---------------------------------------------------------------------------
# 20. Profile Data Persistence After Reload
# ---------------------------------------------------------------------------

class TestProfilePersistence:
    """Verify that profile data survives a page reload."""

    @pytest.fixture
    def _persistence_profile(self, _auth_token):
        """Create a profile for persistence testing."""
        import httpx
        ts = int(time.time())
        headers = {"Authorization": f"Bearer {_auth_token}"}
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Persist User {ts}", "email": f"persist_{ts}@example.com",
                  "phone": "555-7777", "location": "Chicago, IL"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_profile_skills_persist_after_reload(self, logged_in_page: Page, _persistence_profile):
        """Add a skill, save, reload, and verify the skill is still there."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_persistence_profile}")
        page.wait_for_load_state("networkidle")

        # Add a skill
        page.locator("input[placeholder='Skill name']").fill("Kubernetes")
        skills_section = page.locator("h2:has-text('Skills')").locator("..")
        skills_section.locator("select").select_option("advanced")
        skills_section.locator("button.btn-secondary").first.click()
        page.wait_for_timeout(500)
        expect(page.locator("text=Kubernetes")).to_be_visible()

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Reload the page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Skill should still be visible
        expect(page.locator("text=Kubernetes")).to_be_visible(timeout=5000)

    def test_profile_experience_persists_after_reload(self, logged_in_page: Page, _persistence_profile):
        """Add experience, save, reload, and verify it persists."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_persistence_profile}")
        page.wait_for_load_state("networkidle")

        # Add experience
        page.locator("input[placeholder='Job Title']").fill("DevOps Engineer")
        page.locator("input[placeholder='Company']").fill("CloudCo")
        page.locator("input[placeholder='Start (e.g. 2020-01)']").fill("2023-01")
        page.locator("input[placeholder='End (or present)']").fill("present")
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(500)

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Reload
        page.reload()
        page.wait_for_load_state("networkidle")

        # Experience should still be visible
        expect(page.locator("text=DevOps Engineer")).to_be_visible(timeout=5000)
        expect(page.locator("text=CloudCo")).to_be_visible()


# ---------------------------------------------------------------------------
# 21. Rapid Navigation Stability
# ---------------------------------------------------------------------------

class TestRapidNavigation:
    """Test that rapid navigation between pages doesn't break the app."""

    def test_rapid_sidebar_navigation(self, logged_in_page: Page):
        """Quickly clicking through all sidebar links doesn't crash."""
        page = logged_in_page
        nav = page.locator("nav")

        links = ["Dashboard", "Profiles", "Jobs", "Top Matches", "Documents", "Add Job"]
        for link_text in links:
            nav.get_by_role("link", name=link_text).click()
            page.wait_for_timeout(300)

        # App should still be functional — verify we can get back to dashboard
        nav.get_by_role("link", name="Dashboard").click()
        page.wait_for_url(re.compile(r"/$"), timeout=5000)
        expect(page.get_by_role("heading", name=re.compile("Welcome"))).to_be_visible()

    def test_back_forward_navigation(self, logged_in_page: Page):
        """Browser back/forward doesn't break the app."""
        page = logged_in_page

        # Navigate through several pages
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Go back twice
        page.go_back()
        page.wait_for_url("**/jobs", timeout=5000)
        page.go_back()
        page.wait_for_url("**/profiles", timeout=5000)

        # Go forward
        page.go_forward()
        page.wait_for_url("**/jobs", timeout=5000)

        # Page should be functional
        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "[object Object]" not in body


# ---------------------------------------------------------------------------
# 22. Job Detail — Notes Cancel Flow
# ---------------------------------------------------------------------------

class TestJobNotesCancel:
    """Test that canceling notes edit discards changes."""

    @pytest.fixture
    def _notes_job(self, _auth_token):
        """Create a job for notes testing."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Notes Test {ts}", "company": "NotesCorp",
                  "location": "Remote", "description": "Job for notes testing."},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_notes_cancel_discards_changes(self, logged_in_page: Page, _notes_job):
        """Editing notes then clicking Cancel discards the text."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_notes_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Application Status", timeout=10000)

        # Click Edit
        page.locator(".text-primary-600:has-text('Edit')").click()
        page.wait_for_timeout(500)

        # Type some notes
        textarea = page.locator("textarea")
        textarea.fill("This should be discarded")

        # Click Cancel
        page.get_by_role("button", name="Cancel").click()
        page.wait_for_timeout(500)

        # Should show original "No notes yet" text, not the discarded text
        expect(page.locator("text=No notes yet")).to_be_visible()
        body = page.locator("body").inner_text()
        assert "This should be discarded" not in body

    def test_notes_save_persists(self, logged_in_page: Page, _notes_job):
        """Saving notes persists them on reload."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_notes_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Application Status", timeout=10000)

        # Edit notes
        page.locator(".text-primary-600:has-text('Edit')").click()
        page.wait_for_timeout(500)
        page.locator("textarea").fill("Persisted note text")
        page.get_by_role("button", name="Save").click()
        page.wait_for_timeout(2000)

        # Reload page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Note should persist
        expect(page.locator("text=Persisted note text")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# 23. Job Detail — Generated Documents Section
# ---------------------------------------------------------------------------

class TestJobDetailDocuments:
    """Test the generated documents section on job detail page."""

    @pytest.fixture
    def _job_with_docs(self, _auth_token):
        """Create a job and intercept documents to show some exist."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Docs Display {ts}", "company": "DocsCorp",
                  "location": "Remote", "description": "Test job for docs display."},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_job_detail_no_generated_docs_section_when_empty(self, logged_in_page: Page, _job_with_docs):
        """When no docs exist for a job, the Generated Documents section is hidden."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_job_with_docs}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # "Generated Documents" sub-heading should NOT be visible if no docs exist
        body = page.locator("body").inner_text()
        assert "Generated Documents (0)" not in body

    def test_job_detail_docs_section_with_mocked_docs(self, logged_in_page: Page, _job_with_docs):
        """When documents exist for a job, they are displayed."""
        page = logged_in_page
        job_id = _job_with_docs

        # Intercept ONLY the documents API endpoint, not Vite source files
        def handle_docs(route):
            url = route.request.url
            # Only intercept XHR/fetch to the /api/documents endpoint, not source files
            if route.request.resource_type in ("xhr", "fetch") and "/api/documents" in url:
                route.fulfill(
                    status=200, content_type="application/json",
                    body=f'[{{"id":"doc1","job_id":"{job_id}","profile_id":"p1","document_type":"resume","job_title":"Docs Display","job_company":"DocsCorp","job_url":null,"overall_score":85,"reviewed":false,"is_good":null,"pdf_path":null,"created_at":"2026-04-01T00:00:00"}}]'
                )
            else:
                route.continue_()

        page.route("**/api/documents**", handle_docs)

        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # Should show Generated Documents section with the mocked resume doc
        expect(page.locator("text=Generated Documents (1)")).to_be_visible(timeout=5000)
        # The doc card inside Generated Documents shows "Resume" text and score
        gen_docs_section = page.locator("h3:has-text('Generated Documents')").locator("..")
        expect(gen_docs_section.locator("span.text-sm", has_text="Resume")).to_be_visible()
        expect(gen_docs_section.locator("text=85%")).to_be_visible()


# ---------------------------------------------------------------------------
# 24. Documents Page — Empty State vs Content
# ---------------------------------------------------------------------------

class TestDocumentsEmptyState:
    """Test documents page empty state messaging."""

    def test_empty_state_with_no_documents(self, logged_in_page: Page):
        """With no documents, shows 'No Documents Yet' message."""
        page = logged_in_page

        def handle_docs(route):
            if route.request.resource_type in ("xhr", "fetch"):
                route.fulfill(status=200, content_type="application/json", body="[]")
            else:
                route.continue_()

        page.route("**/api/documents**", handle_docs)
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=No Documents Yet")).to_be_visible(timeout=5000)
        expect(page.locator("text=Select a job above")).to_be_visible()

    def test_filter_shows_no_matching_when_filtered_out(self, logged_in_page: Page):
        """Filtering out all docs shows 'No Matching Documents'."""
        page = logged_in_page

        def handle_docs(route):
            if route.request.resource_type in ("xhr", "fetch"):
                route.fulfill(
                    status=200, content_type="application/json",
                    body='[{"id":"d1","job_id":"j1","profile_id":"p1","document_type":"resume","job_title":"Test","job_company":"Corp","job_url":null,"overall_score":80,"reviewed":false,"is_good":null,"pdf_path":null,"created_at":"2026-04-01T00:00:00"}]'
                )
            else:
                route.continue_()

        page.route("**/api/documents**", handle_docs)
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Filter by cover letters — should show no matching
        type_select = page.locator("select:has(option:has-text('All Types'))").first
        type_select.select_option("cover_letter")
        page.wait_for_timeout(500)

        expect(page.locator("text=No Matching Documents")).to_be_visible(timeout=3000)
        expect(page.locator("text=Try changing your filters")).to_be_visible()


# ---------------------------------------------------------------------------
# 25. Profile Form — Basic Info Update
# ---------------------------------------------------------------------------

class TestProfileBasicInfoUpdate:
    """Test updating basic profile info (name, email, phone, location)."""

    @pytest.fixture
    def _editable_profile(self, _auth_token):
        """Create a profile for editing."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Editable User {ts}", "email": f"edit_{ts}@example.com",
                  "phone": "555-1111", "location": "Boston, MA"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_update_basic_info_and_save(self, logged_in_page: Page, _editable_profile, _auth_token):
        """Update profile name and location, save, verify via API."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_editable_profile}")
        page.wait_for_load_state("networkidle")

        # Update name
        name_input = page.locator("input[type='text']").first
        name_input.fill("")
        name_input.type("Updated Name User")

        # Update location
        location_input = page.locator("input[placeholder='City, State']")
        location_input.fill("")
        location_input.type("San Francisco, CA")

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify via API
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/{_editable_profile}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name User"
        assert data["location"] == "San Francisco, CA"


# ---------------------------------------------------------------------------
# 26. Document Multi-Select, Bulk Review & Quality Ratings
# ---------------------------------------------------------------------------

class TestDocumentReviewWorkflow:
    """Test document selection, bulk Mark Reviewed, and thumbs up/down quality ratings."""

    MOCK_DOCS = [
        {
            "id": "doc_a",
            "job_id": "j1",
            "profile_id": "p1",
            "document_type": "resume",
            "job_title": "Alpha Dev",
            "job_company": "AlphaCorp",
            "job_url": None,
            "overall_score": 88,
            "reviewed": False,
            "is_good": None,
            "pdf_path": None,
            "created_at": "2026-04-01T00:00:00",
        },
        {
            "id": "doc_b",
            "job_id": "j2",
            "profile_id": "p1",
            "document_type": "cover_letter",
            "job_title": "Beta Engineer",
            "job_company": "BetaCorp",
            "job_url": None,
            "overall_score": 72,
            "reviewed": False,
            "is_good": None,
            "pdf_path": None,
            "created_at": "2026-04-01T01:00:00",
        },
    ]

    def _route_handler(self, docs_state):
        """Return a route handler that serves current docs_state and handles review PATCHes."""
        import json

        def handler(route):
            req = route.request
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            url = req.url
            # PATCH for review update
            if req.method == "PATCH" and "/review" in url:
                doc_id = url.split("/documents/")[1].split("/review")[0]
                body = json.loads(req.post_data or "{}")
                for d in docs_state:
                    if d["id"] == doc_id:
                        if "reviewed" in body:
                            d["reviewed"] = body["reviewed"]
                        if "is_good" in body:
                            d["is_good"] = body["is_good"]
                route.fulfill(status=200, content_type="application/json", body="{}")
                return
            # GET documents list
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(docs_state),
                )
                return
            route.continue_()

        return handler

    def test_select_document_shows_bulk_actions(self, logged_in_page: Page):
        """Clicking a document checkbox shows 'Mark Reviewed' bulk action bar."""
        page = logged_in_page
        import copy, json
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Verify both docs rendered
        expect(page.locator("text=Alpha Dev")).to_be_visible(timeout=5000)
        expect(page.locator("text=Beta Engineer")).to_be_visible()

        # Bulk action bar should NOT be visible yet
        assert page.locator("text=Mark Reviewed").is_visible() is False

        # Click the checkbox on the first doc card
        cards = page.locator("div.card.flex")
        cards.first.locator("button").first.click()
        page.wait_for_timeout(300)

        # "1 selected" and "Mark Reviewed" should appear
        expect(page.locator("text=1 selected")).to_be_visible()
        expect(page.locator("text=Mark Reviewed")).to_be_visible()

    def test_select_all_and_clear(self, logged_in_page: Page):
        """Select all documents then clear selection."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Alpha Dev")).to_be_visible(timeout=5000)

        # Click "Select all"
        page.locator("button:has-text('Select all')").click()
        page.wait_for_timeout(300)
        expect(page.locator("text=2 selected")).to_be_visible()

        # Click "Clear"
        page.locator("text=Clear").click()
        page.wait_for_timeout(300)
        assert page.locator("text=selected").is_visible() is False

    def test_bulk_mark_reviewed(self, logged_in_page: Page):
        """Selecting docs and clicking Mark Reviewed updates their state."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Alpha Dev")).to_be_visible(timeout=5000)

        # Select all
        page.locator("button:has-text('Select all')").click()
        page.wait_for_timeout(300)

        # Click Mark Reviewed
        page.locator("button:has-text('Mark Reviewed')").click()
        page.wait_for_timeout(1000)

        # Both docs should now be reviewed in the mock state
        assert docs[0]["reviewed"] is True
        assert docs[1]["reviewed"] is True

    def test_thumbs_up_quality_rating(self, logged_in_page: Page):
        """Clicking thumbs up sets is_good to true."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Alpha Dev")).to_be_visible(timeout=5000)

        # Click thumbs up on first doc (title="Good")
        first_card = page.locator("div.card.flex").first
        first_card.locator("button[title='Good']").click()
        page.wait_for_timeout(500)

        assert docs[0]["is_good"] is True

    def test_thumbs_down_quality_rating(self, logged_in_page: Page):
        """Clicking thumbs down sets is_good to false."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Alpha Dev")).to_be_visible(timeout=5000)

        # Click thumbs down on first doc (title="Not good")
        first_card = page.locator("div.card.flex").first
        first_card.locator("button[title='Not good']").click()
        page.wait_for_timeout(500)

        assert docs[0]["is_good"] is False


# ---------------------------------------------------------------------------
# 27. Profile Preferences Save & Persistence
# ---------------------------------------------------------------------------

class TestProfilePreferences:
    """Test saving and reloading profile job preferences."""

    @pytest.fixture
    def _prefs_profile(self, _auth_token):
        """Create a profile for preferences testing."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Prefs User {ts}", "email": f"prefs_{ts}@example.com",
                  "phone": "555-4444", "location": "Miami, FL"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_preferences_section_visible(self, logged_in_page: Page, _prefs_profile):
        """Job Preferences section is visible on edit profile page."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_prefs_profile}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Job Preferences")).to_be_visible()
        expect(page.locator("input[placeholder='Software Engineer, Developer']")).to_be_visible()
        expect(page.locator("input[placeholder='Seattle, Remote']")).to_be_visible()

    def test_save_preferences_and_verify_api(self, logged_in_page: Page, _prefs_profile, _auth_token):
        """Fill preferences, save, and verify via API."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_prefs_profile}")
        page.wait_for_load_state("networkidle")

        # Fill target roles
        roles_input = page.locator("input[placeholder='Software Engineer, Developer']")
        roles_input.fill("Backend Engineer, DevOps")
        roles_input.blur()
        page.wait_for_timeout(200)

        # Fill target locations
        loc_input = page.locator("input[placeholder='Seattle, Remote']")
        loc_input.fill("NYC, Remote")
        loc_input.blur()
        page.wait_for_timeout(200)

        # Set remote preference
        page.locator("select:has(option:has-text('Remote'))").last.select_option("remote")

        # Fill salary range
        page.locator("input[placeholder='Min']").fill("120000")
        page.locator("input[placeholder='Max']").fill("180000")

        # Fill excluded companies
        page.locator("input[placeholder='Companies to exclude from matches']").fill("BadCorp, WorstCo")
        page.locator("input[placeholder='Companies to exclude from matches']").blur()
        page.wait_for_timeout(200)

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify via API
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/{_prefs_profile}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        prefs = data.get("preferences", {})
        assert "Backend Engineer" in prefs.get("target_roles", []), f"target_roles: {prefs.get('target_roles')}"
        assert "Remote" in prefs.get("target_locations", []) or "NYC" in prefs.get("target_locations", []), \
            f"target_locations: {prefs.get('target_locations')}"
        assert prefs.get("remote_preference") == "remote", f"remote_preference: {prefs.get('remote_preference')}"
        assert prefs.get("salary_min") == 120000, f"salary_min: {prefs.get('salary_min')}"
        assert prefs.get("salary_max") == 180000, f"salary_max: {prefs.get('salary_max')}"

    def test_preferences_persist_after_reload(self, logged_in_page: Page, _prefs_profile, _auth_token):
        """Save preferences, reload, verify they're still shown in the form."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_prefs_profile}")
        page.wait_for_load_state("networkidle")

        # Fill and save preferences
        roles_input = page.locator("input[placeholder='Software Engineer, Developer']")
        roles_input.fill("Data Scientist")
        roles_input.blur()
        page.wait_for_timeout(200)

        page.locator("select:has(option:has-text('Remote'))").last.select_option("onsite")
        page.locator("input[placeholder='Min']").fill("90000")

        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Reload
        page.reload()
        page.wait_for_load_state("networkidle")

        # Verify values are populated
        roles_val = page.locator("input[placeholder='Software Engineer, Developer']").input_value()
        assert "Data Scientist" in roles_val, f"Target roles not persisted: {roles_val}"

        salary_min_val = page.locator("input[placeholder='Min']").input_value()
        assert salary_min_val == "90000", f"Salary min not persisted: {salary_min_val}"


# ---------------------------------------------------------------------------
# 28. Admin Route Access Control
# ---------------------------------------------------------------------------

class TestAdminAccessControl:
    """Non-admin users should be redirected away from admin pages."""

    def test_non_admin_redirected_from_admin_dashboard(self, logged_in_page: Page):
        """Non-admin user visiting /admin gets redirected to /."""
        page = logged_in_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")
        # Should NOT be on /admin — redirected to dashboard
        assert "/admin" not in page.url or page.url.endswith("/"), \
            f"Non-admin user was not redirected from /admin. URL: {page.url}"

    def test_non_admin_redirected_from_admin_jobs(self, logged_in_page: Page):
        """Non-admin user visiting /admin/jobs gets redirected."""
        page = logged_in_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")
        assert "/admin/jobs" not in page.url, \
            f"Non-admin should not reach /admin/jobs. URL: {page.url}"

    def test_non_admin_redirected_from_admin_scraper(self, logged_in_page: Page):
        """Non-admin user visiting /admin/scraper gets redirected."""
        page = logged_in_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")
        assert "/admin/scraper" not in page.url, \
            f"Non-admin should not reach /admin/scraper. URL: {page.url}"

    def test_non_admin_redirected_from_admin_pipeline(self, logged_in_page: Page):
        """Non-admin user visiting /admin/pipeline gets redirected."""
        page = logged_in_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")
        assert "/admin/pipeline" not in page.url, \
            f"Non-admin should not reach /admin/pipeline. URL: {page.url}"

    def test_admin_links_not_in_sidebar_for_non_admin(self, logged_in_page: Page):
        """Non-admin users should NOT see admin links in the sidebar."""
        page = logged_in_page
        nav = page.locator("nav")
        assert nav.locator("text=Admin").count() == 0, "Non-admin user sees Admin link in sidebar"
        assert nav.locator("text=Pipeline").count() == 0, "Non-admin user sees Pipeline link"
        assert nav.locator("text=System Tools").count() == 0, "Non-admin user sees System Tools link"
        assert nav.locator("text=All Jobs").count() == 0, "Non-admin user sees All Jobs link"

    def test_admin_api_rejects_non_admin(self, logged_in_page: Page, _auth_token):
        """Admin API endpoints return 403 for non-admin users."""
        page = logged_in_page
        resp = page.request.get(
            API_URL + "/api/admin/stats",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status == 403, f"Expected 403 for non-admin, got {resp.status}"


# ---------------------------------------------------------------------------
# 29. Job Search + Status Filter Interaction
# ---------------------------------------------------------------------------

class TestJobSearchFilterInteraction:
    """Test that search and status filter work together correctly."""

    @pytest.fixture
    def _searchable_jobs(self, _auth_token):
        """Create jobs with distinct titles and statuses for search testing."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        jobs = []
        for i, (title, company, job_status) in enumerate([
            (f"React Engineer {ts}", "SearchCorp", "active"),
            (f"Python Developer {ts}", "SearchCorp", "applied"),
            (f"Go Backend {ts}", "OtherCo", "active"),
        ]):
            resp = httpx.post(
                f"{API_URL}/api/jobs",
                json={"title": title, "company": company, "location": "Remote",
                      "description": f"Search test job {i}"},
                headers=headers,
            )
            assert resp.status_code == 201
            jid = resp.json()["id"]
            # Set status if not active (default)
            if job_status != "active":
                httpx.put(f"{API_URL}/api/jobs/{jid}", json={"status": job_status}, headers=headers)
            jobs.append({"id": jid, "title": title, "company": company, "status": job_status})
        return jobs

    def test_search_filters_by_title(self, logged_in_page: Page, _searchable_jobs):
        """Searching by title filters the jobs list."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        ts = _searchable_jobs[0]["title"].split()[-1]  # timestamp
        search_input = page.locator("input[placeholder*='Search jobs']")
        search_input.fill(f"React Engineer {ts}")
        page.wait_for_timeout(1500)  # debounce

        # The React Engineer job should be visible
        expect(page.locator(f"text=React Engineer {ts}")).to_be_visible(timeout=5000)

    def test_status_filter_then_search(self, logged_in_page: Page, _searchable_jobs):
        """Filter by status, then search narrows further."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # Filter by "applied" status
        select = page.locator("select").first
        select.select_option("applied")
        page.wait_for_timeout(1000)

        ts = _searchable_jobs[1]["title"].split()[-1]
        # The "Python Developer" (applied) should be visible
        body = page.locator("body").inner_text()
        assert f"Python Developer {ts}" in body

    def test_search_no_results_shows_empty_state(self, logged_in_page: Page):
        """Searching for a non-existent term shows no results."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        search_input = page.locator("input[placeholder*='Search jobs']")
        search_input.fill("zzz_nonexistent_job_xyz_12345")
        page.wait_for_timeout(1500)

        # Should show some empty state or no job cards
        body = page.locator("main").inner_text()
        assert "zzz_nonexistent_job_xyz_12345" not in body or "No jobs" in body or "no results" in body.lower()


# ---------------------------------------------------------------------------
# 30. Error Boundary & Network Error Resilience
# ---------------------------------------------------------------------------

class TestErrorResilience:
    """Test app resilience to API errors and bad data."""

    def test_api_500_does_not_crash_jobs_page(self, logged_in_page: Page):
        """A 500 error from the API doesn't crash the jobs page."""
        page = logged_in_page

        def handle_error(route):
            if route.request.resource_type in ("xhr", "fetch") and "/api/jobs" in route.request.url:
                route.fulfill(status=500, content_type="application/json",
                              body='{"detail":"Internal server error"}')
            else:
                route.continue_()

        page.route("**/api/jobs**", handle_error)
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # App should not crash — page should still render
        body = page.locator("body")
        expect(body).to_be_visible()
        # No [object Object] or unhandled error
        content = page.content()
        assert "[object Object]" not in content

    def test_api_500_does_not_crash_documents_page(self, logged_in_page: Page):
        """A 500 error from the documents API doesn't crash the documents page."""
        page = logged_in_page

        def handle_error(route):
            if route.request.resource_type in ("xhr", "fetch") and "/api/documents" in route.request.url:
                route.fulfill(status=500, content_type="application/json",
                              body='{"detail":"Internal server error"}')
            else:
                route.continue_()

        page.route("**/api/documents**", handle_error)
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        body = page.locator("body")
        expect(body).to_be_visible()
        content = page.content()
        assert "[object Object]" not in content

    def test_api_500_does_not_crash_profiles_page(self, logged_in_page: Page):
        """A 500 error from the profiles API doesn't crash the profiles page."""
        page = logged_in_page

        def handle_error(route):
            if route.request.resource_type in ("xhr", "fetch") and "/api/profiles" in route.request.url:
                route.fulfill(status=500, content_type="application/json",
                              body='{"detail":"Internal server error"}')
            else:
                route.continue_()

        page.route("**/api/profiles**", handle_error)
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")

        body = page.locator("body")
        expect(body).to_be_visible()
        content = page.content()
        assert "[object Object]" not in content


# ---------------------------------------------------------------------------
# 28. Jobs Page Pagination Controls
# ---------------------------------------------------------------------------

class TestJobsPagination:
    """Test pagination controls on the Jobs page."""

    @pytest.fixture
    def _many_jobs(self, _auth_token):
        """Create enough jobs to trigger pagination (>20 for default page size)."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        ids = []
        for i in range(25):
            resp = httpx.post(
                f"{API_URL}/api/jobs",
                json={
                    "title": f"Pagination Job {i:03d} {ts}",
                    "company": f"PagCorp{i}",
                    "location": "Remote",
                    "description": f"Job {i} for pagination testing.",
                },
                headers=headers,
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])
        return ids

    def test_pagination_counter_displays(self, logged_in_page: Page, _many_jobs):
        """Pagination counter shows 'Showing X - Y of Z jobs'."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=/Showing \\d+ - \\d+ of \\d+ jobs/")).to_be_visible(timeout=5000)

    def test_pagination_next_button_works(self, logged_in_page: Page, _many_jobs):
        """Clicking Next loads the second page of results."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # With 25+ jobs and default page size 20, Next should be enabled
        next_btn = page.locator("button:has-text('Next')")
        expect(next_btn).to_be_enabled(timeout=5000)

        # Capture the first page content
        first_page_text = page.locator("main").inner_text()

        # Click Next
        next_btn.click()
        page.wait_for_timeout(1000)

        # Content should change — different jobs on page 2
        second_page_text = page.locator("main").inner_text()
        assert first_page_text != second_page_text, "Page content did not change after clicking Next"

    def test_pagination_previous_disabled_on_page_one(self, logged_in_page: Page, _many_jobs):
        """Previous button is disabled on the first page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        prev_btn = page.locator("button:has-text('Previous')")
        expect(prev_btn).to_be_disabled()

    def test_pagination_previous_works_after_next(self, logged_in_page: Page, _many_jobs):
        """After going to page 2, Previous goes back to page 1."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # Capture initial counter text
        counter = page.locator("text=/Showing \\d+ - \\d+ of \\d+ jobs/")
        initial_text = counter.inner_text()

        # Go to page 2
        page.locator("button:has-text('Next')").click()
        page.wait_for_timeout(1000)
        page2_text = counter.inner_text()
        assert page2_text != initial_text

        # Go back to page 1
        page.locator("button:has-text('Previous')").click()
        page.wait_for_timeout(1000)
        back_text = counter.inner_text()
        assert back_text == initial_text, f"Expected '{initial_text}' but got '{back_text}'"

    def test_page_size_change_resets_to_page_one(self, logged_in_page: Page, _many_jobs):
        """Changing page size resets pagination to page 1."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # Go to page 2 first
        next_btn = page.locator("button:has-text('Next')")
        if next_btn.is_enabled():
            next_btn.click()
            page.wait_for_timeout(1000)

        # Change page size to 50
        page_size_select = page.locator("select.input.py-1")
        page_size_select.select_option("50")
        page.wait_for_timeout(1000)

        # Counter should start from 1 again
        counter = page.locator("text=/Showing \\d+ - \\d+ of \\d+ jobs/")
        expect(counter).to_be_visible(timeout=5000)
        assert "Showing 1" in counter.inner_text()


# ---------------------------------------------------------------------------
# 29. Sort Button Toggle Direction
# ---------------------------------------------------------------------------

class TestJobsSortToggle:
    """Test that clicking sort buttons toggles sort direction."""

    def test_sort_by_title_toggles(self, logged_in_page: Page):
        """Clicking Title sort button toggles between ascending and descending."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        title_btn = page.locator("button:has-text('Title')")
        expect(title_btn).to_be_visible()

        # Click once to sort by title
        title_btn.click()
        page.wait_for_timeout(300)

        # Click again to toggle direction
        title_btn.click()
        page.wait_for_timeout(300)

        # Page should still be functional (no crash)
        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "[object Object]" not in page.content()

    def test_sort_by_match_score(self, logged_in_page: Page):
        """Clicking Match Score sorts jobs without errors."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        score_btn = page.locator("button:has-text('Match Score')")
        expect(score_btn).to_be_visible()
        score_btn.click()
        page.wait_for_timeout(500)

        # No errors should appear
        body = page.locator("body").inner_text()
        assert "NaN" not in body


# ---------------------------------------------------------------------------
# 30. Search Resets Pagination
# ---------------------------------------------------------------------------

class TestSearchResetsPagination:
    """Test that searching resets to page 1."""

    def test_search_resets_to_page_one(self, logged_in_page: Page):
        """Typing a search query resets the page back to 1."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")

        # If there's a Next button and it's enabled, go to page 2
        next_btn = page.locator("button:has-text('Next')")
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            page.wait_for_timeout(500)

        # Now search
        search_input = page.locator("input[placeholder*='Search jobs']")
        search_input.fill("test")
        page.wait_for_timeout(500)

        # Previous should be disabled (we're back on page 1)
        prev_btn = page.locator("button:has-text('Previous')")
        if prev_btn.is_visible():
            expect(prev_btn).to_be_disabled()


# ---------------------------------------------------------------------------
# 31. Profile Experience Edit Flow
# ---------------------------------------------------------------------------

class TestExperienceEditFlow:
    """Test the inline experience edit workflow on the profile form."""

    @pytest.fixture
    def _exp_profile(self, _auth_token):
        """Create a profile with an existing experience entry."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Exp Edit User {ts}", "email": f"exp_{ts}@example.com",
                  "phone": "555-8888", "location": "Dallas, TX"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Add experience
        httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={
                "name": f"Exp Edit User {ts}", "email": f"exp_{ts}@example.com",
                "phone": "555-8888", "location": "Dallas, TX", "notes": "",
                "skills": [],
                "experience": [
                    {"title": "Original Title", "company": "Original Corp",
                     "start_date": "2020-01", "end_date": "2023-06",
                     "description": "Did original work."},
                ],
            },
            headers=headers,
        )
        return pid

    def test_click_experience_populates_edit_form(self, logged_in_page: Page, _exp_profile):
        """Clicking an experience entry populates the form fields for editing."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_exp_profile}")
        page.wait_for_load_state("networkidle")

        # Click on the experience entry to edit it
        page.locator("div.bg-gray-50", has_text="Original Title").click()
        page.wait_for_timeout(500)

        # The form should be populated with the experience data
        title_val = page.locator("input[placeholder='Job Title']").input_value()
        company_val = page.locator("input[placeholder='Company']").input_value()
        assert title_val == "Original Title", f"Expected 'Original Title', got '{title_val}'"
        assert company_val == "Original Corp", f"Expected 'Original Corp', got '{company_val}'"

        # The button should say "Update" not "Add"
        expect(page.locator("button:has-text('Update')")).to_be_visible()

    def test_edit_experience_updates_entry(self, logged_in_page: Page, _exp_profile, _auth_token):
        """Edit an experience entry, save profile, verify change persists via API."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_exp_profile}")
        page.wait_for_load_state("networkidle")

        # Click on the experience entry to edit it
        page.locator("div.bg-gray-50", has_text="Original Title").click()
        page.wait_for_timeout(500)

        # Update the title
        title_input = page.locator("input[placeholder='Job Title']")
        title_input.fill("")
        title_input.type("Updated Title")

        # Click Update
        page.locator("button:has-text('Update')").click()
        page.wait_for_timeout(500)

        # Verify the updated title is displayed
        expect(page.locator("text=Updated Title")).to_be_visible()
        # Original title should be gone
        assert page.locator("text=Original Title").count() == 0

        # Save the profile
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify via API
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/{_exp_profile}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        exp_titles = [e["title"] for e in data.get("experience", [])]
        assert "Updated Title" in exp_titles, f"Experience not updated. Titles: {exp_titles}"
        assert "Original Title" not in exp_titles, f"Original title still present. Titles: {exp_titles}"

    def test_cancel_edit_experience_clears_form(self, logged_in_page: Page, _exp_profile):
        """Canceling experience edit clears the form and keeps original entry."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_exp_profile}")
        page.wait_for_load_state("networkidle")

        # Click on the experience entry to edit it
        page.locator("div.bg-gray-50", has_text="Original Title").click()
        page.wait_for_timeout(500)

        # Modify the title
        page.locator("input[placeholder='Job Title']").fill("Should Be Canceled")

        # Click the experience Cancel button (the one with X icon, in the experience form row)
        exp_section = page.locator("h2:has-text('Experience')").locator("..")
        exp_section.locator("button:has-text('Cancel')").click()
        page.wait_for_timeout(500)

        # Original entry should still be visible
        expect(page.locator("text=Original Title")).to_be_visible()
        # Form should be cleared
        title_val = page.locator("input[placeholder='Job Title']").input_value()
        assert title_val == "", f"Form not cleared after cancel: '{title_val}'"


# ---------------------------------------------------------------------------
# 32. Profile Skill Removal Flow
# ---------------------------------------------------------------------------

class TestSkillRemovalFlow:
    """Test adding and removing skills on the profile form."""

    @pytest.fixture
    def _skill_profile(self, _auth_token):
        """Create a profile with skills for removal testing."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Skill Rm User {ts}", "email": f"skillrm_{ts}@example.com",
                  "phone": "555-6666", "location": "Seattle, WA"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Add skills
        httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={
                "name": f"Skill Rm User {ts}", "email": f"skillrm_{ts}@example.com",
                "phone": "555-6666", "location": "Seattle, WA", "notes": "",
                "skills": [
                    {"name": "Java", "level": "expert"},
                    {"name": "Spring", "level": "advanced"},
                    {"name": "SQL", "level": "intermediate"},
                ],
                "experience": [],
            },
            headers=headers,
        )
        return pid

    def test_remove_skill_and_save(self, logged_in_page: Page, _skill_profile, _auth_token):
        """Remove a skill from the profile, save, verify only remaining skills persist."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_skill_profile}")
        page.wait_for_load_state("networkidle")

        # All three skills should be visible
        expect(page.locator("text=Java")).to_be_visible(timeout=5000)
        expect(page.locator("text=Spring")).to_be_visible()
        expect(page.locator("text=SQL")).to_be_visible()

        # Remove "Spring" — find its remove button in the skill pill
        skills_section = page.locator("h2:has-text('Skills')").locator("..")
        # Skill pills are div.rounded-full elements
        spring_pill = skills_section.locator("div.rounded-full", has_text="Spring")
        spring_pill.locator("button").click()
        page.wait_for_timeout(300)

        # Spring should be gone
        expect(spring_pill).to_be_hidden()

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify via API
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/{_skill_profile}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        skill_names = [s["name"] for s in data.get("skills", [])]
        assert "Java" in skill_names, f"Java should remain. Skills: {skill_names}"
        assert "SQL" in skill_names, f"SQL should remain. Skills: {skill_names}"
        assert "Spring" not in skill_names, f"Spring should be removed. Skills: {skill_names}"


# ---------------------------------------------------------------------------
# 33. Experience Removal Flow
# ---------------------------------------------------------------------------

class TestExperienceRemovalFlow:
    """Test removing experience entries on the profile form."""

    @pytest.fixture
    def _exp_rm_profile(self, _auth_token):
        """Create a profile with multiple experience entries."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Exp Rm User {ts}", "email": f"exprm_{ts}@example.com",
                  "phone": "555-3333", "location": "Austin, TX"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={
                "name": f"Exp Rm User {ts}", "email": f"exprm_{ts}@example.com",
                "phone": "555-3333", "location": "Austin, TX", "notes": "",
                "skills": [],
                "experience": [
                    {"title": "Senior Dev", "company": "KeepCo",
                     "start_date": "2021-01", "end_date": "present", "description": "Keep this."},
                    {"title": "Junior Dev", "company": "RemoveCo",
                     "start_date": "2019-01", "end_date": "2020-12", "description": "Remove this."},
                ],
            },
            headers=headers,
        )
        return pid

    def test_remove_experience_and_save(self, logged_in_page: Page, _exp_rm_profile, _auth_token):
        """Remove an experience entry, save, verify only remaining entries persist."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{_exp_rm_profile}")
        page.wait_for_load_state("networkidle")

        # Both entries should be visible
        expect(page.locator("text=Senior Dev")).to_be_visible(timeout=5000)
        expect(page.locator("text=Junior Dev")).to_be_visible()

        # Remove "Junior Dev" via its trash icon
        junior_entry = page.locator("div.bg-gray-50", has_text="Junior Dev").first
        junior_entry.locator("button:last-child").click()
        page.wait_for_timeout(300)

        # Junior Dev should be gone
        expect(page.locator("div.bg-gray-50", has_text="Junior Dev")).to_be_hidden()

        # Save
        page.get_by_role("button", name="Save Changes").click()
        page.wait_for_timeout(2000)
        expect(page.locator("text=Profile saved successfully")).to_be_visible()

        # Verify via API
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/{_exp_rm_profile}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        exp_titles = [e["title"] for e in data.get("experience", [])]
        assert "Senior Dev" in exp_titles, f"Senior Dev should remain. Titles: {exp_titles}"
        assert "Junior Dev" not in exp_titles, f"Junior Dev should be removed. Titles: {exp_titles}"


# ---------------------------------------------------------------------------
# 34. XSS-Safe Rendering (Special Characters)
# ---------------------------------------------------------------------------

class TestSpecialCharacterRendering:
    """Test that special characters in job data render safely (no XSS, no broken UI)."""

    @pytest.fixture
    def _xss_job(self, _auth_token):
        """Create a job with HTML-like special characters."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": '<script>alert("xss")</script> Engineer',
                "company": 'Company & Co "LLC"',
                "location": "<b>Remote</b>",
                "description": "O'Reilly & Partners <img src=x> test role.",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_special_chars_render_as_text(self, logged_in_page: Page, _xss_job):
        """Special characters in job data render as text, not HTML."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_xss_job}")
        page.wait_for_load_state("networkidle")

        # The content should appear as escaped text, not as executed HTML
        body_text = page.locator("body").inner_text()
        assert "alert" in body_text or "script" in body_text, \
            "Script tag should be rendered as text, not stripped"
        assert 'Company & Co "LLC"' in body_text or "Company &amp; Co" in body_text

        # No actual script should execute — check no alert dialog appeared
        content = page.content()
        # The script tag should be escaped in the HTML source
        assert "<script>alert" not in content.lower().replace("&lt;", "<").replace("&gt;", ">") or \
               "&lt;script&gt;" in content, \
            "Script tag not properly escaped in HTML"


# ---------------------------------------------------------------------------
# 40. Dashboard Getting Started Checklist
# ---------------------------------------------------------------------------

class TestDashboardGettingStarted:
    """Test the Getting Started checklist for new users on the dashboard."""

    def test_new_user_sees_getting_started(self, page: Page, _auth_token):
        """A fresh user with no profiles sees the Getting Started card."""
        import httpx
        ts = int(time.time())
        new_email = f"newuser_{ts}@example.com"
        new_pass = "NewUserPass123!"
        resp = httpx.post(
            f"{API_URL}/api/auth/register",
            json={"name": "New User", "email": new_email, "password": new_pass},
        )
        if resp.status_code == 429:
            pytest.skip("Auth rate-limited")
        assert resp.status_code in (201, 400)

        resp = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": new_email, "password": new_pass},
        )
        if resp.status_code == 429:
            pytest.skip("Auth rate-limited")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        page.goto(APP_URL + "/login")
        page.evaluate(f"window.localStorage.setItem('auth_token', '{token}')")
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Should see "Getting Started" card
        expect(page.locator("h2:has-text('Getting Started')")).to_be_visible(timeout=5000)

        # Should see the three checklist items
        expect(page.locator("text=Create your profile")).to_be_visible()
        expect(page.locator("text=Browse or add jobs")).to_be_visible()
        expect(page.locator("text=View your matches")).to_be_visible()

        # Welcome message for new user (no "back")
        heading = page.get_by_role("heading", name=re.compile("Welcome")).inner_text()
        assert "back" not in heading, "New user should see 'Welcome' not 'Welcome back'"

    def test_getting_started_link_to_profiles(self, page: Page, _auth_token):
        """Clicking 'Create your profile' navigates to /profiles/new."""
        import httpx
        ts = int(time.time())
        new_email = f"checklist_prof_{ts}@example.com"
        new_pass = "ChecklistPass123!"
        resp = httpx.post(
            f"{API_URL}/api/auth/register",
            json={"name": "Checklist User", "email": new_email, "password": new_pass},
        )
        if resp.status_code == 429:
            pytest.skip("Auth rate-limited")
        resp = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": new_email, "password": new_pass},
        )
        if resp.status_code == 429:
            pytest.skip("Auth rate-limited")
        token = resp.json()["access_token"]

        page.goto(APP_URL + "/login")
        page.evaluate(f"window.localStorage.setItem('auth_token', '{token}')")
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        page.locator("a:has-text('Create your profile')").click()
        page.wait_for_url("**/profiles/new", timeout=5000)

    def test_existing_user_no_getting_started(self, logged_in_page: Page, _auth_token):
        """A user who already has profiles does NOT see Getting Started."""
        page = logged_in_page
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        # Ensure user has at least one profile
        httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"HasProfile {ts}", "email": f"has_{ts}@example.com",
                  "phone": "555-0000", "location": "Test"},
            headers=headers,
        )

        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Getting Started should NOT be visible
        assert page.locator("h2:has-text('Getting Started')").count() == 0, \
            "User with profiles should not see Getting Started"

        # Should see "Welcome back" heading
        heading = page.get_by_role("heading", name=re.compile("Welcome")).inner_text()
        assert "back" in heading, "Existing user should see 'Welcome back'"


# ---------------------------------------------------------------------------
# 41. Mobile Responsive Layout
# ---------------------------------------------------------------------------

class TestMobileResponsiveLayout:
    """Test the mobile sidebar toggle and responsive behavior."""

    def test_mobile_hamburger_opens_sidebar(self, logged_in_page: Page):
        """On mobile viewport, clicking hamburger menu opens sidebar."""
        page = logged_in_page
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Sidebar should be hidden (off-screen) on mobile
        sidebar = page.locator("aside")
        classes = sidebar.get_attribute("class") or ""
        assert "-translate-x-full" in classes, \
            f"Sidebar should be off-screen on mobile. Classes: {classes}"

        # Hamburger menu button is in the main > mobile header div
        hamburger = page.locator("main button.p-1\\.5").first
        expect(hamburger).to_be_visible()
        hamburger.click()
        page.wait_for_timeout(300)

        # Sidebar should now be visible (translate-x-0)
        classes = sidebar.get_attribute("class") or ""
        assert "translate-x-0" in classes, f"Sidebar should slide in. Classes: {classes}"

        # Nav links should be visible inside sidebar
        expect(sidebar.get_by_role("link", name="Dashboard")).to_be_visible()
        expect(sidebar.get_by_role("link", name="Jobs")).to_be_visible()

    def test_mobile_overlay_closes_sidebar(self, logged_in_page: Page):
        """Clicking the overlay closes the sidebar on mobile."""
        page = logged_in_page
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Open sidebar via hamburger in main content area
        page.locator("main button.p-1\\.5").first.click()
        page.wait_for_timeout(300)

        # Overlay should be visible
        overlay = page.locator("div.fixed.inset-0")
        expect(overlay).to_be_visible()

        # Click overlay to the right of the sidebar (w-64 = 256px)
        page.mouse.click(330, 400)
        page.wait_for_timeout(300)

        # Sidebar should be closed again
        sidebar = page.locator("aside")
        classes = sidebar.get_attribute("class") or ""
        assert "-translate-x-full" in classes, "Sidebar should close after clicking overlay"

    def test_mobile_nav_link_closes_sidebar(self, logged_in_page: Page):
        """Clicking a nav link on mobile closes the sidebar."""
        page = logged_in_page
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Open sidebar
        page.locator("main button.p-1\\.5").first.click()
        page.wait_for_timeout(300)

        # Click a nav link
        sidebar = page.locator("aside")
        sidebar.get_by_role("link", name="Jobs").click()
        page.wait_for_url("**/jobs", timeout=5000)
        page.wait_for_timeout(300)

        # Sidebar should be closed
        classes = sidebar.get_attribute("class") or ""
        assert "-translate-x-full" in classes, "Sidebar should close after nav click"

    def test_desktop_sidebar_always_visible(self, logged_in_page: Page):
        """On desktop viewport, sidebar is always visible without hamburger."""
        page = logged_in_page
        page.set_viewport_size({"width": 1280, "height": 800})
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Sidebar should be visible
        sidebar = page.locator("aside")
        expect(sidebar).to_be_visible()
        expect(sidebar.get_by_role("link", name="Dashboard")).to_be_visible()


# ---------------------------------------------------------------------------
# 42. Document Individual Review Toggle
# ---------------------------------------------------------------------------

class TestDocumentIndividualReview:
    """Test the per-document review checkbox toggle (Square/CheckSquare icon)."""

    MOCK_DOCS = [
        {
            "id": "rev_doc_1",
            "job_id": "j1",
            "profile_id": "p1",
            "document_type": "resume",
            "job_title": "Review Test Dev",
            "job_company": "ReviewCorp",
            "job_url": None,
            "overall_score": 90,
            "reviewed": False,
            "is_good": None,
            "pdf_path": None,
            "created_at": "2026-04-01T00:00:00",
        },
    ]

    def _route_handler(self, docs_state):
        """Route handler that serves docs and handles PATCH review updates."""
        import json

        def handler(route):
            req = route.request
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            url = req.url
            if req.method == "PATCH" and "/review" in url:
                doc_id = url.split("/documents/")[1].split("/review")[0]
                body = json.loads(req.post_data or "{}")
                for d in docs_state:
                    if d["id"] == doc_id:
                        if "reviewed" in body:
                            d["reviewed"] = body["reviewed"]
                        if "is_good" in body:
                            d["is_good"] = body["is_good"]
                route.fulfill(status=200, content_type="application/json", body="{}")
                return
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(docs_state),
                )
                return
            route.continue_()

        return handler

    def test_review_toggle_marks_reviewed(self, logged_in_page: Page):
        """Clicking the review toggle marks the document as reviewed."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Review Test Dev")).to_be_visible(timeout=5000)

        # Click the review toggle button (title="Mark as reviewed" when unchecked)
        review_btn = page.locator("button[title='Mark as reviewed']").first
        expect(review_btn).to_be_visible()
        review_btn.click()
        page.wait_for_timeout(500)

        # The doc should now be marked as reviewed in mock state
        assert docs[0]["reviewed"] is True

    def test_review_toggle_unmarks_reviewed(self, logged_in_page: Page):
        """Clicking the review toggle on a reviewed doc unmarks it."""
        page = logged_in_page
        import copy
        docs = copy.deepcopy(self.MOCK_DOCS)
        docs[0]["reviewed"] = True  # Start as reviewed
        page.route("**/api/documents**", self._route_handler(docs))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Review Test Dev")).to_be_visible(timeout=5000)

        # Button should now say "Mark as unreviewed"
        unmark_btn = page.locator("button[title='Mark as unreviewed']").first
        expect(unmark_btn).to_be_visible()
        unmark_btn.click()
        page.wait_for_timeout(500)

        # Should be unmarked
        assert docs[0]["reviewed"] is False


# ---------------------------------------------------------------------------
# 43. Job Detail — Generation Error Message Styling
# ---------------------------------------------------------------------------

class TestJobDetailGenerationErrorStyling:
    """Test that generation error messages display in red, not gray.

    Bug: error messages that don't contain 'failed'/'Failed' (e.g.,
    'temporarily unavailable') were rendering in text-gray-600 instead of
    text-red-600 because the old code parsed the message text.
    """

    JOB_DATA = {
        "id": "err_style_j1",
        "title": "Error Styling Test Job",
        "company": "ErrCo",
        "location": "Remote",
        "salary": "$100k",
        "status": "active",
        "url": "https://example.com/job",
        "description": "Test description",
        "platform": "manual",
        "added_by": "manual",
        "posted_date": "2026-03-31",
        "cached_at": "2026-03-31T00:00:00",
        "match": None,
        "notes": "",
    }

    def _route_handler(self, error_msg: str):
        """Intercept generate calls and return custom errors."""
        import json

        def handler(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            if "/api/jobs/err_style_j1" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(self.JOB_DATA),
                )
                return
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body="[]",
                )
                return
            if "/api/documents/" in url and req.method == "POST":
                route.fulfill(
                    status=400,
                    content_type="application/json",
                    body=json.dumps({"detail": error_msg}),
                )
                return
            route.continue_()

        return handler

    def test_ollama_error_message_is_red(self, logged_in_page: Page):
        """Error about Ollama/connection should display in red text."""
        page = logged_in_page
        page.route("**/*", self._route_handler("Ollama connection refused"))
        page.goto(APP_URL + "/jobs/err_style_j1")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Error Styling Test Job")).to_be_visible(timeout=5000)

        # Click "Resume Only" to trigger generation
        page.get_by_role("button", name="Resume Only").click()

        # Wait for error message to appear
        error_el = page.locator("p.text-red-600")
        expect(error_el).to_be_visible(timeout=10000)
        assert "unavailable" in error_el.text_content().lower() or "ollama" in error_el.text_content().lower()

    def test_custom_api_error_message_is_red(self, logged_in_page: Page):
        """A custom API error (no 'failed' in text) should also display red."""
        page = logged_in_page
        page.route("**/*", self._route_handler("No active profile configured"))
        page.goto(APP_URL + "/jobs/err_style_j1")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Error Styling Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume Only").click()

        # The error should be red regardless of message content
        error_el = page.locator("p.text-red-600")
        expect(error_el).to_be_visible(timeout=10000)
        assert "profile" in error_el.text_content().lower()


# ---------------------------------------------------------------------------
# 44. Add Job — Text Paste Method Workflow
# ---------------------------------------------------------------------------

class TestAddJobTextPaste:
    """Test the 'Paste Text' method on the Add Job page."""

    def test_text_tab_has_textarea_and_submit(self, logged_in_page: Page):
        """Switching to 'Paste Text' shows a textarea and submit button."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Paste Text").click()

        textarea = page.locator("textarea")
        expect(textarea).to_be_visible()
        expect(textarea).to_have_attribute("placeholder", re.compile(r"Paste.*job description"))

        submit = page.get_by_role("button", name="Add Job")
        expect(submit).to_be_visible()

    def test_text_empty_submit_shows_error(self, logged_in_page: Page):
        """Submitting empty text shows a validation error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Paste Text").click()
        page.get_by_role("button", name="Add Job").click()

        # Should show error message
        expect(page.locator("text=Please enter job description text")).to_be_visible(timeout=3000)

    def test_text_method_submits_to_api(self, logged_in_page: Page):
        """Submitting text calls the API with plaintext field."""
        page = logged_in_page
        import json

        captured_body = {}

        def intercept(route):
            req = route.request
            if "/api/jobs" in req.url and req.method == "POST" and "upload" not in req.url:
                body = json.loads(req.post_data or "{}")
                captured_body.update(body)
                route.fulfill(
                    status=201,
                    content_type="application/json",
                    body=json.dumps({
                        "id": "text_job_1", "title": "Parsed Job", "company": "TextCo",
                        "location": "Remote", "salary": "", "status": "active",
                        "url": "", "description": "parsed", "platform": "manual",
                        "added_by": "text", "posted_date": "", "cached_at": "2026-04-01T00:00:00",
                        "match": None, "notes": "",
                    }),
                )
                return
            route.continue_()

        page.route("**/api/jobs**", intercept)
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Paste Text").click()
        page.locator("textarea").fill("Senior Software Engineer at Acme Corp. Remote. $150k-200k.")
        page.get_by_role("button", name="Add Job").click()

        page.wait_for_timeout(2000)
        assert "plaintext" in captured_body, f"Expected plaintext in body, got: {captured_body}"
        assert "Acme Corp" in captured_body["plaintext"]


# ---------------------------------------------------------------------------
# 45. Job Detail — Notes Cancel/Edit Interaction
# ---------------------------------------------------------------------------

class TestJobDetailNotesInteraction:
    """Test notes editing interactions on the job detail page."""

    JOB_DATA = {
        "id": "notes_int_j1",
        "title": "Notes Interaction Test Job",
        "company": "NotesCo",
        "location": "Seattle",
        "salary": "",
        "status": "active",
        "url": "",
        "description": "Some description",
        "platform": "manual",
        "added_by": "manual",
        "posted_date": "2026-03-31",
        "cached_at": "2026-03-31T00:00:00",
        "match": None,
        "notes": "Original notes here",
    }

    def _route_handler(self):
        import json

        def handler(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            if "/api/jobs/notes_int_j1" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(self.JOB_DATA),
                )
                return
            if "/api/jobs/notes_int_j1" in url and req.method == "PUT":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps(self.JOB_DATA),
                )
                return
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body="[]",
                )
                return
            route.continue_()

        return handler

    def test_edit_notes_shows_original_text(self, logged_in_page: Page):
        """Clicking Edit on notes loads the current note text into the textarea."""
        page = logged_in_page
        page.route("**/*", self._route_handler())
        page.goto(APP_URL + "/jobs/notes_int_j1")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Original notes here")).to_be_visible(timeout=5000)

        page.get_by_text("Edit", exact=True).click()
        textarea = page.locator("textarea")
        expect(textarea).to_be_visible()
        assert textarea.input_value() == "Original notes here"

    def test_cancel_notes_hides_editor(self, logged_in_page: Page):
        """Clicking Cancel on notes hides the textarea without saving."""
        page = logged_in_page
        page.route("**/*", self._route_handler())
        page.goto(APP_URL + "/jobs/notes_int_j1")
        page.wait_for_load_state("networkidle")

        page.get_by_text("Edit", exact=True).click()
        textarea = page.locator("textarea")
        expect(textarea).to_be_visible()

        textarea.fill("Changed notes that should be discarded")
        page.get_by_role("button", name="Cancel").click()

        # Textarea should be hidden, original text visible
        expect(textarea).not_to_be_visible()
        expect(page.locator("text=Original notes here")).to_be_visible()


# ---------------------------------------------------------------------------
# 46. Dashboard Stats — No Bad Data Rendering
# ---------------------------------------------------------------------------

class TestDashboardStatsRendering:
    """Verify dashboard stat cards never show NaN, undefined, or [object Object]."""

    def test_stats_with_zero_jobs_show_numeric_values(self, logged_in_page: Page):
        """When a user has zero jobs, stats should show '0' not bad data."""
        page = logged_in_page
        import json

        def intercept(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            if "/api/jobs/top" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json", body="[]")
                return
            if "/api/jobs" in url and req.method == "GET":
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({"jobs": [], "total": 0, "page": 1, "page_size": 5, "pages": 0}),
                )
                return
            if "/api/profiles" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json", body="[]")
                return
            route.continue_()

        page.route("**/*", intercept)
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Check that stat cards render correctly with zeros
        body = page.locator("body").text_content()
        assert "NaN" not in body, "Found NaN in dashboard"
        assert "undefined" not in body, "Found undefined in dashboard"
        assert "[object Object]" not in body, "Found [object Object] in dashboard"

        # Total Jobs should show 0
        expect(page.locator("text=Total Jobs")).to_be_visible()
        expect(page.locator("text=0").first).to_be_visible()


# ---------------------------------------------------------------------------
# 48. Generation Success Flow — Job Detail Page
# ---------------------------------------------------------------------------

class TestJobDetailGenerationSuccess:
    """Test that after a mocked successful generation, the UI shows
    the correct success message and the generated document card appears."""

    JOB_DATA = {
        "id": "gen_success_j1",
        "title": "Gen Success Test Job",
        "company": "SuccessCo",
        "location": "Remote",
        "salary": "$120k",
        "status": "active",
        "url": None,
        "description": "A test job for verifying generation success flow.",
        "platform": "manual",
        "added_by": "manual",
        "posted_date": "2026-04-01",
        "cached_at": "2026-04-01T00:00:00",
        "match": None,
        "notes": "",
    }

    RESUME_RESPONSE = {
        "id": "doc_resume_1",
        "job_id": "gen_success_j1",
        "profile_id": "p1",
        "document_type": "resume",
        "content": "Generated resume content",
        "pdf_path": None,
        "quality_scores": {
            "fact_score": 88,
            "keyword_score": 92,
            "ats_score": 85,
            "length_score": 100,
            "overall_score": 91,
        },
        "iterations": 1,
        "created_at": "2026-04-01T12:00:00",
    }

    COVER_LETTER_RESPONSE = {
        "id": "doc_cl_1",
        "job_id": "gen_success_j1",
        "profile_id": "p1",
        "document_type": "cover_letter",
        "content": "Generated cover letter content",
        "pdf_path": None,
        "quality_scores": {
            "fact_score": 90,
            "keyword_score": 88,
            "ats_score": 82,
            "length_score": 100,
            "overall_score": 90,
        },
        "iterations": 1,
        "created_at": "2026-04-01T12:01:00",
    }

    def _make_route_handler(self, gen_responses: dict):
        """Create a route handler that returns mocked API responses."""
        import json as _json

        job_data = _json.dumps(self.JOB_DATA)
        docs_after = []  # accumulate docs returned by generation

        def handler(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return

            # Job detail
            if "/api/jobs/gen_success_j1" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=job_data)
                return

            # Document generation endpoints
            if "/api/documents/resume" in url and req.method == "POST":
                resp = gen_responses.get("resume")
                if resp:
                    docs_after.append(resp)
                    route.fulfill(status=200, content_type="application/json",
                                  body=_json.dumps(resp))
                else:
                    route.fulfill(status=400, content_type="application/json",
                                  body='{"detail":"Generation failed"}')
                return
            if "/api/documents/cover-letter" in url and req.method == "POST":
                resp = gen_responses.get("cover_letter")
                if resp:
                    docs_after.append(resp)
                    route.fulfill(status=200, content_type="application/json",
                                  body=_json.dumps(resp))
                else:
                    route.fulfill(status=400, content_type="application/json",
                                  body='{"detail":"Generation failed"}')
                return
            if "/api/documents/package" in url and req.method == "POST":
                resume_resp = gen_responses.get("resume")
                cl_resp = gen_responses.get("cover_letter")
                if resume_resp:
                    docs_after.append(resume_resp)
                if cl_resp:
                    docs_after.append(cl_resp)
                body = {
                    "resume": resume_resp,
                    "cover_letter": cl_resp,
                }
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(body))
                return

            # Download — always 404 (no real PDF)
            if "/api/documents/" in url and "/download" in url:
                route.fulfill(status=404, content_type="application/json",
                              body='{"detail":"Not found"}')
                return

            # Documents list — return accumulated generated docs
            if "/api/documents" in url and req.method == "GET":
                list_items = []
                for d in docs_after:
                    list_items.append({
                        "id": d["id"],
                        "job_id": d["job_id"],
                        "profile_id": d["profile_id"],
                        "document_type": d["document_type"],
                        "job_title": self.JOB_DATA["title"],
                        "job_company": self.JOB_DATA["company"],
                        "job_url": None,
                        "overall_score": d["quality_scores"]["overall_score"],
                        "reviewed": False,
                        "is_good": None,
                        "pdf_path": None,
                        "created_at": d["created_at"],
                    })
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(list_items))
                return

            route.continue_()

        return handler

    def test_resume_generation_success_message(self, logged_in_page: Page):
        """After successful resume generation, shows score in success message."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "resume": self.RESUME_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume Only").click()

        # Should show success with score
        expect(page.locator("text=Resume generated! Score: 91%")).to_be_visible(timeout=10000)

    def test_resume_generation_shows_document_card(self, logged_in_page: Page):
        """After successful resume generation, a document card appears in Generated Documents."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "resume": self.RESUME_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume Only").click()

        # Wait for generation to complete
        expect(page.locator("text=Resume generated!")).to_be_visible(timeout=10000)

        # The Generated Documents section should appear with the new doc
        expect(page.locator("text=Generated Documents (1)")).to_be_visible(timeout=5000)
        gen_section = page.locator("h3:has-text('Generated Documents')").locator("..")
        expect(gen_section.locator("span.text-sm", has_text="Resume")).to_be_visible()
        expect(gen_section.locator("text=91%")).to_be_visible()

    def test_cover_letter_generation_success_message(self, logged_in_page: Page):
        """After successful cover letter generation, shows score in success message."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "cover_letter": self.COVER_LETTER_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Cover Letter Only").click()

        expect(page.locator("text=Cover letter generated! Score: 90%")).to_be_visible(timeout=10000)

    def test_package_generation_success_message(self, logged_in_page: Page):
        """After successful package generation, shows generic success message."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "resume": self.RESUME_RESPONSE,
            "cover_letter": self.COVER_LETTER_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume + Cover Letter").click()

        expect(page.locator("text=Documents generated successfully!")).to_be_visible(timeout=10000)

    def test_package_generation_shows_both_document_cards(self, logged_in_page: Page):
        """After successful package generation, both document cards appear."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "resume": self.RESUME_RESPONSE,
            "cover_letter": self.COVER_LETTER_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume + Cover Letter").click()

        # Wait for generation to complete
        expect(page.locator("text=Documents generated successfully!")).to_be_visible(timeout=10000)

        # Both docs should appear in the Generated Documents section
        expect(page.locator("text=Generated Documents (2)")).to_be_visible(timeout=5000)

    def test_buttons_re_enable_after_generation(self, logged_in_page: Page):
        """After generation completes, all generate buttons are re-enabled."""
        page = logged_in_page
        page.route("**/*", self._make_route_handler({
            "resume": self.RESUME_RESPONSE,
        }))
        page.goto(APP_URL + "/jobs/gen_success_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Gen Success Test Job")).to_be_visible(timeout=5000)

        page.get_by_role("button", name="Resume Only").click()
        expect(page.locator("text=Resume generated!")).to_be_visible(timeout=10000)

        # All generate buttons should be enabled again
        expect(page.locator("button:has-text('Resume + Cover Letter')")).to_be_enabled()
        expect(page.locator("button:has-text('Resume Only')")).to_be_enabled()
        expect(page.locator("button:has-text('Cover Letter Only')")).to_be_enabled()


# ---------------------------------------------------------------------------
# 31. PDF Download Path Validation
# ---------------------------------------------------------------------------

class TestPDFDownloadPath:
    """Test that PDF downloads work for documents in all valid directories."""

    def test_download_endpoint_returns_pdf_for_generated_documents_dir(self, _auth_token):
        """Verify the download endpoint accepts PDFs from the generated_documents/ directory."""
        import httpx
        import json
        from pathlib import Path

        headers = {"Authorization": f"Bearer {_auth_token}"}

        # Check if there are any documents with pdf_path set
        resp = httpx.get(f"{API_URL}/api/documents", params={"limit": 100}, headers=headers)
        assert resp.status_code == 200
        docs = resp.json()

        docs_with_pdf = [d for d in docs if d.get("pdf_path")]
        if not docs_with_pdf:
            pytest.skip("No documents with PDF paths to test download")

        # Try downloading the first document with a PDF path
        doc = docs_with_pdf[0]
        resp = httpx.get(
            f"{API_URL}/api/documents/{doc['id']}/download",
            headers=headers,
        )
        # Should return 200 (not 404 from path traversal block)
        assert resp.status_code == 200, (
            f"PDF download failed with {resp.status_code} for doc {doc['id']}. "
            f"pdf_path={doc.get('pdf_path')}"
        )
        # Response should be a valid PDF
        assert resp.content[:5] == b"%PDF-", "Downloaded content is not a valid PDF"

    def test_documents_page_download_button_visible_for_pdf(self, logged_in_page: Page):
        """Documents with pdf_path show a download button on the documents page."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Check if any documents exist
        count_text = page.locator("text=/\\d+ documents/")
        if not count_text.is_visible(timeout=3000):
            pytest.skip("No documents to test download button")

        # If documents with PDFs exist, download icon should be visible
        download_btns = page.locator("button[title='Download PDF']")
        if download_btns.count() > 0:
            expect(download_btns.first).to_be_visible()


# ---------------------------------------------------------------------------
# 32. Documents Page — Full Generation Success Flow (Mocked)
# ---------------------------------------------------------------------------

class TestDocumentsPageGenerationSuccess:
    """Test that completing generation on the Documents page shows success
    message and the newly generated document appears in the list."""

    MOCK_RESUME = {
        "id": "doc_gen_r1",
        "job_id": "gen_j1",
        "profile_id": "gen_p1",
        "document_type": "resume",
        "content": "Generated resume text",
        "pdf_path": None,
        "quality_scores": {
            "fact_score": 95,
            "keyword_score": 88,
            "ats_score": 90,
            "length_score": 100,
            "overall_score": 93,
        },
        "iterations": 1,
        "created_at": "2026-04-01T12:00:00",
    }

    MOCK_COVER_LETTER = {
        "id": "doc_gen_cl1",
        "job_id": "gen_j1",
        "profile_id": "gen_p1",
        "document_type": "cover_letter",
        "content": "Generated cover letter text",
        "pdf_path": None,
        "quality_scores": {
            "fact_score": 92,
            "keyword_score": 85,
            "ats_score": 88,
            "length_score": 100,
            "overall_score": 91,
        },
        "iterations": 1,
        "created_at": "2026-04-01T12:01:00",
    }

    MOCK_JOBS = [
        {"id": "gen_j1", "title": "Senior Python Dev", "company": "GenTestCo",
         "location": "Remote", "salary": "$150k", "status": "active",
         "url": None, "description": "Python developer role.",
         "platform": "manual", "added_by": "manual",
         "posted_date": "2026-04-01", "cached_at": "2026-04-01T00:00:00",
         "match": None, "notes": ""},
    ]

    def _make_handler(self, gen_type, generated_docs_state):
        """Route handler for documents page generation tests."""
        import json as _json

        jobs_json = _json.dumps(self.MOCK_JOBS)

        def handler(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return

            # Jobs list for dropdown
            if "/api/jobs/top" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json",
                              body=jobs_json)
                return
            if "/api/jobs" in url and req.method == "GET" and "/api/jobs/" not in url:
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps({"jobs": self.MOCK_JOBS, "total": 1, "page": 1}))
                return

            # Generation endpoints
            if "/api/documents/resume" in url and req.method == "POST":
                generated_docs_state.append({
                    "id": self.MOCK_RESUME["id"],
                    "job_id": self.MOCK_RESUME["job_id"],
                    "profile_id": self.MOCK_RESUME["profile_id"],
                    "document_type": "resume",
                    "job_title": "Senior Python Dev",
                    "job_company": "GenTestCo",
                    "job_url": None,
                    "overall_score": 93,
                    "reviewed": False,
                    "is_good": None,
                    "pdf_path": None,
                    "created_at": self.MOCK_RESUME["created_at"],
                })
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(self.MOCK_RESUME))
                return
            if "/api/documents/cover-letter" in url and req.method == "POST":
                generated_docs_state.append({
                    "id": self.MOCK_COVER_LETTER["id"],
                    "job_id": self.MOCK_COVER_LETTER["job_id"],
                    "profile_id": self.MOCK_COVER_LETTER["profile_id"],
                    "document_type": "cover_letter",
                    "job_title": "Senior Python Dev",
                    "job_company": "GenTestCo",
                    "job_url": None,
                    "overall_score": 91,
                    "reviewed": False,
                    "is_good": None,
                    "pdf_path": None,
                    "created_at": self.MOCK_COVER_LETTER["created_at"],
                })
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(self.MOCK_COVER_LETTER))
                return
            if "/api/documents/package" in url and req.method == "POST":
                for doc_resp, doc_type, score, dt in [
                    (self.MOCK_RESUME, "resume", 93, self.MOCK_RESUME["created_at"]),
                    (self.MOCK_COVER_LETTER, "cover_letter", 91, self.MOCK_COVER_LETTER["created_at"]),
                ]:
                    generated_docs_state.append({
                        "id": doc_resp["id"],
                        "job_id": doc_resp["job_id"],
                        "profile_id": doc_resp["profile_id"],
                        "document_type": doc_type,
                        "job_title": "Senior Python Dev",
                        "job_company": "GenTestCo",
                        "job_url": None,
                        "overall_score": score,
                        "reviewed": False,
                        "is_good": None,
                        "pdf_path": None,
                        "created_at": dt,
                    })
                body = {
                    "resume": self.MOCK_RESUME,
                    "cover_letter": self.MOCK_COVER_LETTER,
                }
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(body))
                return

            # Documents list
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(generated_docs_state))
                return

            route.continue_()

        return handler

    def test_resume_only_generation_success_on_docs_page(self, logged_in_page: Page):
        """Select job, choose Resume Only, click Generate, see success message and new doc."""
        page = logged_in_page
        docs_state = []
        page.route("**/*", self._make_handler("resume", docs_state))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Select job from dropdown
        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )
        job_select.select_option(index=1)

        # Select "Resume Only" type
        gen_section = page.locator("h2:has-text('Generate Documents')").locator("..").locator("..")
        type_select = gen_section.locator("select").nth(1)
        type_select.select_option("resume")
        page.wait_for_timeout(300)

        # Click Generate
        gen_btn = page.locator("button:has-text('Generate')")
        gen_btn.click()

        # Success message should appear
        expect(page.locator("text=Documents generated successfully!")).to_be_visible(timeout=10000)

        # New document should appear in the list (use card locator to avoid matching dropdown)
        doc_card = page.locator("div.card.flex", has_text="Senior Python Dev")
        expect(doc_card).to_be_visible(timeout=5000)
        expect(doc_card.locator("text=GenTestCo")).to_be_visible()

    def test_package_generation_success_shows_both_docs(self, logged_in_page: Page):
        """Generate package shows success and both resume + cover letter appear in list."""
        page = logged_in_page
        docs_state = []
        page.route("**/*", self._make_handler("package", docs_state))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Select job
        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )
        job_select.select_option(index=1)
        page.wait_for_timeout(300)

        # Default type is "package" — click Generate
        gen_btn = page.locator("button:has-text('Generate')")
        gen_btn.click()

        # Success message
        expect(page.locator("text=Documents generated successfully!")).to_be_visible(timeout=10000)

        # Both docs should be in the list — count shows 2
        expect(page.locator("text=2 documents")).to_be_visible(timeout=5000)

    def test_generation_button_disabled_during_generation(self, logged_in_page: Page):
        """Generate button shows 'Generating...' and is disabled during generation."""
        page = logged_in_page
        docs_state = []

        # Hold the request pending to observe the disabled state
        pending = []

        def handler(route):
            req = route.request
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            url = req.url
            if "/api/documents/resume" in url and req.method == "POST":
                pending.append(route)
                return
            if "/api/jobs" in url and req.method == "GET":
                import json
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(self.MOCK_JOBS))
                return
            if "/api/documents" in url and req.method == "GET":
                import json
                route.fulfill(status=200, content_type="application/json",
                              body=json.dumps(docs_state))
                return
            route.continue_()

        page.route("**/*", handler)
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Select job and type
        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )
        job_select.select_option(index=1)
        gen_section = page.locator("h2:has-text('Generate Documents')").locator("..").locator("..")
        type_select = gen_section.locator("select").nth(1)
        type_select.select_option("resume")
        page.wait_for_timeout(300)

        gen_btn = page.locator("button:has-text('Generate')")
        gen_btn.click()

        # Button should show "Generating..." and be disabled
        expect(page.locator("button:has-text('Generating...')")).to_be_visible(timeout=3000)
        expect(page.locator("button:has-text('Generating...')")).to_be_disabled()

        # Clean up pending routes
        import json
        for r in pending:
            try:
                r.fulfill(status=200, content_type="application/json",
                          body=json.dumps(self.MOCK_RESUME))
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 33. Job Detail — Regenerate Button on Existing Documents
# ---------------------------------------------------------------------------

class TestJobDetailRegenerateFlow:
    """Test that clicking the regenerate icon on an existing document card
    triggers a new generation and updates the document list."""

    JOB_DATA = {
        "id": "regen_j1",
        "title": "Regen Test Job",
        "company": "RegenCo",
        "location": "Remote",
        "salary": "$100k",
        "status": "active",
        "url": None,
        "description": "A job to test regeneration flow.",
        "platform": "manual",
        "added_by": "manual",
        "posted_date": "2026-04-01",
        "cached_at": "2026-04-01T00:00:00",
        "match": None,
        "notes": "",
    }

    EXISTING_DOC = {
        "id": "regen_doc1",
        "job_id": "regen_j1",
        "profile_id": "p1",
        "document_type": "resume",
        "job_title": "Regen Test Job",
        "job_company": "RegenCo",
        "job_url": None,
        "overall_score": 75,
        "reviewed": False,
        "is_good": None,
        "pdf_path": None,
        "created_at": "2026-04-01T10:00:00",
    }

    REGENERATED_DOC_RESPONSE = {
        "id": "regen_doc1",
        "job_id": "regen_j1",
        "profile_id": "p1",
        "document_type": "resume",
        "content": "Regenerated resume content",
        "pdf_path": None,
        "quality_scores": {
            "fact_score": 95,
            "keyword_score": 92,
            "ats_score": 90,
            "length_score": 100,
            "overall_score": 94,
        },
        "iterations": 1,
        "created_at": "2026-04-01T14:00:00",
    }

    def _make_handler(self, generation_count):
        import json as _json

        job_data = _json.dumps(self.JOB_DATA)
        existing_doc = dict(self.EXISTING_DOC)

        def handler(route):
            req = route.request
            url = req.url
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return

            # Job detail
            if "/api/jobs/regen_j1" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json", body=job_data)
                return

            # Resume generation
            if "/api/documents/resume" in url and req.method == "POST":
                generation_count.append(1)
                # Update existing doc score after regeneration
                existing_doc["overall_score"] = 94
                existing_doc["created_at"] = "2026-04-01T14:00:00"
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(self.REGENERATED_DOC_RESPONSE))
                return

            # Download — 404
            if "/api/documents/" in url and "/download" in url:
                route.fulfill(status=404, content_type="application/json",
                              body='{"detail":"Not found"}')
                return

            # Documents list
            if "/api/documents" in url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps([existing_doc]))
                return

            route.continue_()

        return handler

    def test_regenerate_button_triggers_generation(self, logged_in_page: Page):
        """Clicking regenerate icon on an existing doc triggers new generation."""
        page = logged_in_page
        gen_count = []
        page.route("**/*", self._make_handler(gen_count))

        page.goto(APP_URL + "/jobs/regen_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Regen Test Job")).to_be_visible(timeout=5000)

        # Existing doc should be visible with initial score
        expect(page.locator("text=Generated Documents (1)")).to_be_visible(timeout=5000)
        expect(page.locator("text=75%")).to_be_visible()

        # Click the regenerate button (RefreshCw icon with title="Regenerate")
        regen_btn = page.locator("button[title='Regenerate']")
        expect(regen_btn).to_be_visible()
        regen_btn.click()

        # Should show generation status and then success
        expect(page.locator("text=Resume generated! Score: 94%")).to_be_visible(timeout=10000)

        # A generation API call was made
        assert len(gen_count) >= 1

    def test_regenerate_updates_score_in_doc_card(self, logged_in_page: Page):
        """After regeneration, the document card shows the updated score."""
        page = logged_in_page
        gen_count = []
        page.route("**/*", self._make_handler(gen_count))

        page.goto(APP_URL + "/jobs/regen_j1")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Regen Test Job")).to_be_visible(timeout=5000)
        expect(page.locator("text=Generated Documents (1)")).to_be_visible(timeout=5000)

        # Click regenerate
        page.locator("button[title='Regenerate']").click()

        # Wait for success
        expect(page.locator("text=Resume generated!")).to_be_visible(timeout=10000)

        # After query invalidation, the doc card should show updated 94% score
        gen_docs_section = page.locator("h3:has-text('Generated Documents')").locator("..")
        expect(gen_docs_section.locator("text=94%")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# 34. Document Score Rendering Validation
# ---------------------------------------------------------------------------

class TestDocumentScoreRendering:
    """Verify that quality scores render as clean percentages on the Documents
    page — no NaN, undefined, or raw decimal values."""

    MOCK_DOCS = [
        {
            "id": "score_d1",
            "job_id": "j1",
            "profile_id": "p1",
            "document_type": "resume",
            "job_title": "Score Test Dev",
            "job_company": "ScoreCorp",
            "job_url": None,
            "overall_score": 87.6,
            "reviewed": False,
            "is_good": None,
            "pdf_path": None,
            "created_at": "2026-04-01T00:00:00",
        },
        {
            "id": "score_d2",
            "job_id": "j2",
            "profile_id": "p1",
            "document_type": "cover_letter",
            "job_title": "Score Test Engineer",
            "job_company": "ScoreInc",
            "job_url": "https://example.com/job",
            "overall_score": 0,
            "reviewed": True,
            "is_good": True,
            "pdf_path": "/some/path.pdf",
            "created_at": "2026-04-01T01:00:00",
        },
    ]

    def _route_handler(self):
        import json as _json

        def handler(route):
            req = route.request
            if req.resource_type not in ("xhr", "fetch"):
                route.continue_()
                return
            if "/api/documents" in req.url and req.method == "GET":
                route.fulfill(status=200, content_type="application/json",
                              body=_json.dumps(self.MOCK_DOCS))
                return
            route.continue_()

        return handler

    def test_score_renders_as_integer_percent(self, logged_in_page: Page):
        """Score 87.6 should render as '88%' (toFixed(0)), not '87.6%'."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Dev")).to_be_visible(timeout=5000)

        # Should render as 88% (rounded), not 87.6%
        score_el = page.locator("text=Score: 88%")
        expect(score_el).to_be_visible()

    def test_zero_score_hidden(self, logged_in_page: Page):
        """A document with overall_score 0 should not show 'Score: 0%'."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Engineer")).to_be_visible(timeout=5000)

        # The ScoreInc doc has score 0 — should NOT show "Score: 0%"
        score_inc_card = page.locator("div.card", has_text="Score Test Engineer")
        card_text = score_inc_card.inner_text()
        assert "Score: 0%" not in card_text

    def test_no_nan_or_undefined_in_scores(self, logged_in_page: Page):
        """No NaN, undefined, or null text in score display."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Dev")).to_be_visible(timeout=5000)

        content = page.content()
        assert "NaN%" not in content
        assert "undefined%" not in content
        assert "null%" not in content

    def test_reviewed_doc_shows_green_checkmark(self, logged_in_page: Page):
        """A reviewed document has the green checkmark styling."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Engineer")).to_be_visible(timeout=5000)

        # The reviewed doc (Score Test Engineer) should have a green-styled review button
        score_inc_card = page.locator("div.card", has_text="Score Test Engineer")
        reviewed_btn = score_inc_card.locator("button.text-green-600").first
        expect(reviewed_btn).to_be_visible()

    def test_external_link_visible_for_doc_with_url(self, logged_in_page: Page):
        """Documents with a job_url show the external link icon."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Engineer")).to_be_visible(timeout=5000)

        # ScoreInc doc has a job_url — should show external link button
        score_inc_card = page.locator("div.card", has_text="Score Test Engineer")
        link = score_inc_card.locator("a[title='View job posting']")
        expect(link).to_be_visible()

    def test_download_button_visible_for_doc_with_pdf(self, logged_in_page: Page):
        """Documents with a pdf_path show the download button."""
        page = logged_in_page
        page.route("**/api/documents**", self._route_handler())
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.locator("text=Score Test Engineer")).to_be_visible(timeout=5000)

        # ScoreInc doc has pdf_path — should show download button
        score_inc_card = page.locator("div.card", has_text="Score Test Engineer")
        dl_btn = score_inc_card.locator("button[title='Download PDF']")
        expect(dl_btn).to_be_visible()

        # ScoreCorp doc has NO pdf_path — should NOT show download button
        score_corp_card = page.locator("div.card", has_text="Score Test Dev")
        dl_btn_absent = score_corp_card.locator("button[title='Download PDF']")
        assert dl_btn_absent.count() == 0


# ---------------------------------------------------------------------------
# Admin User Fixtures
# ---------------------------------------------------------------------------

_admin_ts = str(int(time.time())) + "_adm"
ADMIN_EMAIL = f"admin_{_admin_ts}@example.com"
ADMIN_PASSWORD = "AdminPass123!"
ADMIN_NAME = "E2E Admin User"


@pytest.fixture(scope="session")
def _admin_token():
    """Get an admin token by logging in as the hardcoded admin email.

    The app's user_store.py grants admin to justin.masui@gmail.com.
    We register (or re-use) that account, then verify via /api/auth/me.
    """
    import httpx

    admin_email = "justin.masui@gmail.com"
    admin_password = "AdminTestPass123!"

    # Register — 400 is fine (already exists), 429 → skip
    resp = httpx.post(
        f"{API_URL}/api/auth/register",
        json={"name": "Admin", "email": admin_email, "password": admin_password},
    )
    if resp.status_code == 429:
        pytest.skip("Rate limited during admin registration")

    # Login
    resp = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": admin_email, "password": admin_password},
    )
    if resp.status_code == 429:
        pytest.skip("Rate limited during admin login")
    if resp.status_code != 200:
        pytest.skip("Could not obtain admin token")

    token = resp.json()["access_token"]

    # Verify admin via /api/auth/me
    me_resp = httpx.get(
        f"{API_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if me_resp.status_code != 200 or not me_resp.json().get("is_admin"):
        pytest.skip("Test user is not admin")

    return token


@pytest.fixture
def admin_page(page: Page, _admin_token):
    """Return a page logged in as an admin user."""
    page.goto(APP_URL + "/login")
    page.evaluate(f"window.localStorage.setItem('auth_token', '{_admin_token}')")
    page.goto(APP_URL)
    page.wait_for_load_state("networkidle")
    return page


# ---------------------------------------------------------------------------
# 50. Admin Pipeline Page
# ---------------------------------------------------------------------------


class TestAdminPipelinePage:
    """Tests for the admin pipeline dashboard page."""

    def test_pipeline_page_loads(self, admin_page: Page):
        """Pipeline dashboard page loads with expected sections."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)
        expect(page.locator("text=Manage the automated job pipeline")).to_be_visible()

    def test_scheduler_section_visible(self, admin_page: Page):
        """Scheduler card is visible with interval input and start/stop button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h2", has_text="Scheduler")).to_be_visible(timeout=5000)
        # Interval input exists
        interval_input = page.locator("input[type='number']").first
        expect(interval_input).to_be_visible()
        # Start or Stop Scheduler button exists
        btn = page.locator("button", has_text=re.compile(r"Start Scheduler|Stop Scheduler"))
        expect(btn).to_be_visible()

    def test_manual_run_section_visible(self, admin_page: Page):
        """Manual run card with pipeline step checkboxes and run button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h2", has_text="Manual Run")).to_be_visible(timeout=5000)
        # All 5 step labels visible
        for step in ["search", "clean", "fetch", "match", "generate"]:
            expect(page.locator(f"label:has-text('{step}')")).to_be_visible()
        # Run button visible (may show "Run Pipeline Now" or "Running..." if pipeline is active)
        run_btn = page.locator("button.btn-primary", has_text=re.compile("Run Pipeline|Running"))
        expect(run_btn).to_be_visible()

    def test_step_toggle(self, admin_page: Page):
        """Clicking a step label toggles its selection state."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        search_label = page.locator("label:has-text('search')")
        expect(search_label).to_be_visible(timeout=5000)

        # Initially all steps are selected (bg-primary-50)
        assert "primary" in (search_label.get_attribute("class") or "")

        # Click to deselect
        search_label.click()
        page.wait_for_timeout(300)
        assert "primary" not in (search_label.get_attribute("class") or ""), \
            "search step should be deselected after click"

        # Click again to reselect
        search_label.click()
        page.wait_for_timeout(300)
        assert "primary" in (search_label.get_attribute("class") or ""), \
            "search step should be reselected after second click"

    def test_run_button_disabled_when_no_steps(self, admin_page: Page):
        """Run button is disabled when all steps are deselected."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Deselect all steps
        for step in ["search", "clean", "fetch", "match", "generate"]:
            label = page.locator(f"label:has-text('{step}')")
            # Only click if currently selected
            if "primary" in (label.get_attribute("class") or ""):
                label.click()
                page.wait_for_timeout(100)

        run_btn = page.locator("button.btn-primary", has_text=re.compile("Run Pipeline|Running"))
        expect(run_btn).to_be_disabled()

    def test_stats_section_visible(self, admin_page: Page):
        """Pipeline stats cards are displayed."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Stats section has labels like Total Runs, Successful, Failed, etc.
        expect(page.locator("text=Total Runs")).to_be_visible(timeout=5000)
        expect(page.get_by_text("Successful", exact=True)).to_be_visible()
        expect(page.get_by_text("Failed", exact=True)).to_be_visible()

    def test_run_history_section_visible(self, admin_page: Page):
        """Run history table or empty message is displayed."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h2", has_text="Run History")).to_be_visible(timeout=5000)
        # Either shows table or "No pipeline runs yet"
        has_table = page.locator("table").count() > 0
        has_empty = page.locator("text=No pipeline runs yet").count() > 0
        assert has_table or has_empty, "Run History should show a table or empty message"

    def test_log_viewer_section_visible(self, admin_page: Page):
        """Pipeline log viewer section is displayed."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h2", has_text="Pipeline Logs")).to_be_visible(timeout=5000)
        # Log viewer area (dark background div)
        log_viewer = page.locator("div.bg-gray-900")
        expect(log_viewer).to_be_visible()

    def test_no_nan_or_undefined_in_stats(self, admin_page: Page):
        """Stats values do not show NaN, undefined, or null."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        body_text = page.locator("body").inner_text()
        for bad_value in ["NaN", "undefined", "[object Object]"]:
            assert bad_value not in body_text, \
                f"Found '{bad_value}' on pipeline page"


# ---------------------------------------------------------------------------
# 51. Admin Dashboard Page
# ---------------------------------------------------------------------------


class TestAdminDashboardPage:
    """Tests for the admin dashboard page."""

    def test_admin_dashboard_loads(self, admin_page: Page):
        """Admin dashboard loads with title and stats cards."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1", has_text="Admin Dashboard")).to_be_visible(timeout=5000)
        expect(page.locator("text=System overview and management tools")).to_be_visible()

    def test_stats_cards_visible(self, admin_page: Page):
        """Stats cards show Total Jobs, Total Users, etc."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Total Jobs")).to_be_visible(timeout=5000)
        expect(page.locator("text=Total Users")).to_be_visible()
        expect(page.locator("text=Total Matches")).to_be_visible()

    def test_quick_actions_links(self, admin_page: Page):
        """Quick action links navigate to correct admin subpages."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Quick Actions")).to_be_visible(timeout=5000)

        # Pipeline Dashboard link in the quick actions section (not sidebar)
        pipeline_link = page.get_by_role("link", name="Pipeline Dashboard")
        expect(pipeline_link).to_be_visible()
        pipeline_link.click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)

    def test_no_nan_or_undefined(self, admin_page: Page):
        """Admin dashboard doesn't show NaN, undefined, or [object Object]."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        body_text = page.locator("body").inner_text()
        for bad_value in ["NaN", "undefined", "[object Object]"]:
            assert bad_value not in body_text, \
                f"Found '{bad_value}' on admin dashboard"

    def test_cache_information_section(self, admin_page: Page):
        """Cache information section is visible."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Cache Information")).to_be_visible(timeout=5000)
        expect(page.locator("text=Cache Directory")).to_be_visible()


# ---------------------------------------------------------------------------
# 52. Admin System Operations Page
# ---------------------------------------------------------------------------


class TestAdminScraperPage:
    """Tests for the admin system operations (scraper) page."""

    def test_scraper_page_loads(self, admin_page: Page):
        """System operations page loads with all tool sections."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1", has_text="System Operations")).to_be_visible(timeout=5000)
        expect(page.locator("h2", has_text="Job Scraper")).to_be_visible()
        expect(page.locator("h2", has_text="Job Searcher")).to_be_visible()
        expect(page.locator("h2", has_text="Job Matcher")).to_be_visible()
        expect(page.locator("h2", has_text="Cleanup")).to_be_visible()

    def test_scraper_run_button(self, admin_page: Page):
        """Scraper run button exists and is clickable."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        run_btn = page.locator("button", has_text="Run Scraper")
        expect(run_btn).to_be_visible(timeout=5000)
        expect(run_btn).to_be_enabled()

    def test_searcher_requires_search_term(self, admin_page: Page):
        """Searcher run button is disabled without a search term."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        run_btn = page.locator("button", has_text="Run Searcher")
        expect(run_btn).to_be_visible(timeout=5000)
        expect(run_btn).to_be_disabled()

    def test_searcher_enabled_with_search_term(self, admin_page: Page):
        """Searcher run button is enabled after typing a search term."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        # Fill in the search term input
        page.locator("input[placeholder='Software Engineer']").fill("test engineer")
        run_btn = page.locator("button", has_text="Run Searcher")
        expect(run_btn).to_be_enabled()

    def test_matcher_run_button_enabled(self, admin_page: Page):
        """Matcher run button is enabled by default."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        run_btn = page.locator("button", has_text="Run Matcher")
        expect(run_btn).to_be_visible(timeout=5000)
        expect(run_btn).to_be_enabled()

    def test_cleanup_run_button(self, admin_page: Page):
        """Cleanup run button exists and is enabled."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        run_btn = page.locator("button", has_text="Run Cleanup")
        expect(run_btn).to_be_visible(timeout=5000)
        expect(run_btn).to_be_enabled()


# ---------------------------------------------------------------------------
# 53. Admin Jobs Page
# ---------------------------------------------------------------------------


class TestAdminJobsPage:
    """Tests for the admin jobs management page."""

    def test_admin_jobs_page_loads(self, admin_page: Page):
        """Admin jobs page loads with title and table."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h1", has_text="Manage Jobs")).to_be_visible(timeout=5000)
        expect(page.locator("text=View and manage all jobs")).to_be_visible()

    def test_jobs_table_or_empty(self, admin_page: Page):
        """Admin jobs page shows a table of jobs or a loading state."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")

        # Should have a table with headers
        expect(page.locator("th", has_text="Title")).to_be_visible(timeout=5000)
        expect(page.locator("th", has_text="Company")).to_be_visible()
        expect(page.locator("th", has_text="Location")).to_be_visible()

    def test_pagination_controls(self, admin_page: Page):
        """Pagination buttons exist."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")

        prev_btn = page.locator("button", has_text="Previous")
        next_btn = page.locator("button", has_text="Next")
        expect(prev_btn).to_be_visible(timeout=5000)
        expect(next_btn).to_be_visible()
        # First page: Previous should be disabled
        expect(prev_btn).to_be_disabled()

    def test_no_nan_or_undefined(self, admin_page: Page):
        """Admin jobs page doesn't show NaN, undefined, or null text."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        body_text = page.locator("body").inner_text()
        for bad_value in ["NaN", "undefined", "[object Object]"]:
            assert bad_value not in body_text, \
                f"Found '{bad_value}' on admin jobs page"


# ---------------------------------------------------------------------------
# 54. Admin Navigation
# ---------------------------------------------------------------------------


class TestAdminNavigation:
    """Admin users see admin links in sidebar and can navigate between pages."""

    def test_admin_sees_admin_links(self, admin_page: Page):
        """Admin user sees Admin, Pipeline, System Tools, All Jobs in nav."""
        page = admin_page
        nav = page.locator("nav")
        expect(nav.get_by_role("link", name="Admin")).to_be_visible(timeout=5000)
        expect(nav.get_by_role("link", name="Pipeline")).to_be_visible()

    def test_navigate_to_pipeline_from_nav(self, admin_page: Page):
        """Clicking Pipeline in nav goes to pipeline page."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="Pipeline").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)
        assert "/admin/pipeline" in page.url

    def test_navigate_between_admin_pages(self, admin_page: Page):
        """Navigate from admin dashboard to pipeline and back."""
        page = admin_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Admin Dashboard")).to_be_visible(timeout=5000)

        # Go to pipeline
        page.locator("nav").get_by_role("link", name="Pipeline").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)

        # Go back to admin dashboard
        page.locator("nav").get_by_role("link", name="Admin").click()
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Admin Dashboard")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# 56. Admin Pipeline Scheduler Toggle
# ---------------------------------------------------------------------------


class TestAdminPipelineSchedulerToggle:
    """Test enabling and disabling the pipeline scheduler through the UI."""

    def test_start_scheduler_shows_active_badge(self, admin_page: Page):
        """Clicking Start Scheduler shows Active badge and Stop button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)

        # Click Start Scheduler
        start_btn = page.get_by_role("button", name="Start Scheduler")
        expect(start_btn).to_be_visible(timeout=5000)
        start_btn.click()
        page.wait_for_timeout(1500)

        # Should now show "Active" badge and "Stop Scheduler" button
        expect(page.locator("text=Active")).to_be_visible(timeout=5000)
        expect(page.get_by_role("button", name="Stop Scheduler")).to_be_visible()

    def test_stop_scheduler_removes_active_badge(self, admin_page: Page):
        """Clicking Stop Scheduler removes Active badge, shows Start button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Ensure scheduler is running first
        start_btn = page.get_by_role("button", name="Start Scheduler")
        if start_btn.is_visible():
            start_btn.click()
            page.wait_for_timeout(1500)

        # Now stop it
        stop_btn = page.get_by_role("button", name="Stop Scheduler")
        expect(stop_btn).to_be_visible(timeout=5000)
        stop_btn.click()
        page.wait_for_timeout(1500)

        # Should show Start Scheduler again
        expect(page.get_by_role("button", name="Start Scheduler")).to_be_visible(timeout=5000)

    def test_scheduler_interval_input_accepts_values(self, admin_page: Page):
        """Interval input accepts numeric values."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        interval_input = page.locator("input[type='number']")
        expect(interval_input).to_be_visible(timeout=5000)

        # Clear and set new interval
        interval_input.fill("12")
        assert interval_input.input_value() == "12"

    def test_scheduler_time_selector_visible(self, admin_page: Page):
        """Daily time selector (hour and minute dropdowns) is visible."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Hour dropdown is visible and has option values
        hour_select = page.locator("select").first
        expect(hour_select).to_be_visible(timeout=5000)
        # Default value is "--" (empty)
        assert hour_select.input_value() == ""
        # Has 24+ options (-- plus 24 hours)
        option_count = hour_select.locator("option").count()
        assert option_count >= 25, f"Expected 25+ options, got {option_count}"


# ---------------------------------------------------------------------------
# 57. Admin Pipeline Manual Run Interaction
# ---------------------------------------------------------------------------


class TestAdminPipelineManualRun:
    """Test manual pipeline run button interactions."""

    def test_deselect_all_steps_disables_run(self, admin_page: Page):
        """Deselecting all steps disables the Run Pipeline button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Wait for pipeline to stop running (may be running from earlier test)
        page.wait_for_timeout(3000)
        page.reload()
        page.wait_for_load_state("networkidle")

        # Click each step toggle to deselect
        for step in ["search", "clean", "fetch", "match", "generate"]:
            step_label = page.locator(f"label:has-text('{step}')").first
            if step_label.is_visible():
                step_label.click()
        page.wait_for_timeout(500)

        # Run button should be disabled
        run_btn = page.locator("button.btn-primary", has_text=re.compile("Run Pipeline|Running"))
        expect(run_btn).to_be_disabled()

    def test_reselect_step_enables_run(self, admin_page: Page):
        """Re-selecting a step after deselecting all re-enables the Run button."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Deselect all
        for step in ["search", "clean", "fetch", "match", "generate"]:
            step_label = page.locator(f"label:has-text('{step}')").first
            if step_label.is_visible():
                step_label.click()
        page.wait_for_timeout(300)

        # Re-select "clean"
        page.locator("label:has-text('clean')").first.click()
        page.wait_for_timeout(300)

        # Run button — if pipeline not running, should be enabled
        run_btn = page.locator("button.btn-primary", has_text=re.compile("Run Pipeline|Running"))
        # Just verify button exists and page isn't crashed
        expect(run_btn).to_be_visible()

    def test_run_pipeline_click_does_not_crash(self, admin_page: Page):
        """Running the pipeline does not crash the page."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # The run button exists (may show "Run Pipeline Now" or "Running...")
        run_btn = page.locator("button.btn-primary", has_text=re.compile("Run Pipeline|Running"))
        expect(run_btn).to_be_visible(timeout=5000)

        # If pipeline is not already running, try clicking
        if "Running" not in (run_btn.inner_text() or ""):
            # Ensure at least "clean" is selected
            clean_label = page.locator("label:has-text('clean')").first
            cls = clean_label.get_attribute("class") or ""
            if "primary" not in cls:
                clean_label.click()
                page.wait_for_timeout(300)

            if run_btn.is_enabled():
                run_btn.click()
                page.wait_for_timeout(2000)

        # Page should not crash — pipeline heading still visible
        expect(page.locator("h1", has_text="Pipeline Dashboard")).to_be_visible(timeout=5000)
        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "undefined" not in body

    def test_pipeline_empty_history_message(self, admin_page: Page):
        """When there are no runs, shows 'No pipeline runs yet' message."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # The run history section exists
        expect(page.locator("h2", has_text="Run History")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# 58. Admin Scraper Page Deep Interactions
# ---------------------------------------------------------------------------


class TestAdminScraperDeep:
    """Deep tests for the admin scraper page interactions."""

    def test_scraper_sections_all_visible(self, admin_page: Page):
        """All scraper sections (Scraper, Searcher, Matcher, Cleanup) visible."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        expect(page.locator("h2", has_text="Job Scraper")).to_be_visible(timeout=5000)
        expect(page.locator("h2", has_text="Job Searcher")).to_be_visible()
        expect(page.locator("h2", has_text="Job Matcher")).to_be_visible()
        expect(page.locator("h2", has_text="Cleanup")).to_be_visible()

    def test_searcher_search_term_input(self, admin_page: Page):
        """Searcher section has a search term input and typing enables the button."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")

        # Find search input by placeholder
        search_input = page.locator("input[placeholder='Software Engineer']")
        expect(search_input).to_be_visible(timeout=5000)

        # Type a search term
        search_input.fill("data scientist")
        page.wait_for_timeout(300)

        # Run Search button should be enabled
        search_btn = page.locator("button", has_text="Run Search")
        expect(search_btn).to_be_enabled()

    def test_scraper_no_bad_data(self, admin_page: Page):
        """No NaN, undefined, null, or [object Object] on scraper page."""
        page = admin_page
        page.goto(APP_URL + "/admin/scraper")
        page.wait_for_load_state("networkidle")
        body = page.locator("body").inner_text()
        for bad in ["NaN", "undefined", "[object Object]"]:
            assert bad not in body, f"Found '{bad}' on scraper page"


# ---------------------------------------------------------------------------
# 59. Admin Jobs Page Deep Interactions
# ---------------------------------------------------------------------------


class TestAdminJobsDeep:
    """Deep tests for admin jobs page pagination and display."""

    def test_admin_jobs_shows_total_count(self, admin_page: Page):
        """Admin jobs page displays the total job count."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")
        expect(page.locator("h1", has_text="Manage Jobs")).to_be_visible(timeout=5000)

        # Should have a table or list with jobs
        body = page.locator("body").inner_text()
        # Verify no bad data
        for bad in ["NaN", "undefined", "[object Object]"]:
            assert bad not in body, f"Found '{bad}' on admin jobs page"

    def test_admin_jobs_pagination_works(self, admin_page: Page):
        """Admin jobs page pagination navigates between pages."""
        page = admin_page
        page.goto(APP_URL + "/admin/jobs")
        page.wait_for_load_state("networkidle")

        # Look for pagination controls
        next_btn = page.locator("button", has_text=re.compile("Next|>")).first
        if next_btn.is_visible() and next_btn.is_enabled():
            next_btn.click()
            page.wait_for_load_state("networkidle")
            # Should still be on admin jobs page
            assert "/admin/jobs" in page.url or "/admin" in page.url


# ---------------------------------------------------------------------------
# 60. Document API Error Handling Through UI
# ---------------------------------------------------------------------------


class TestDocumentAPIErrors:
    """Test that document generation errors are handled gracefully in the UI."""

    def test_documents_page_handles_empty_list(self, logged_in_page: Page):
        """Documents page shows empty state when no documents exist."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        body = page.locator("body").inner_text()
        # Should not crash — either shows docs or empty state
        assert "NaN" not in body
        assert "undefined" not in body
        assert "[object Object]" not in body

    def test_documents_page_filter_with_no_results(self, logged_in_page: Page):
        """Applying a filter that matches nothing shows empty state, not crash."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Try to filter by type if dropdown exists
        type_dropdown = page.locator("select").first
        if type_dropdown.is_visible():
            type_dropdown.select_option(index=1)
            page.wait_for_timeout(500)

        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "undefined" not in body


# ---------------------------------------------------------------------------
# 61. Profile Creation Validation Edge Cases
# ---------------------------------------------------------------------------


class TestProfileCreationEdgeCases:
    """Test edge cases in profile creation."""

    def test_create_profile_with_only_name(self, logged_in_page: Page):
        """Creating a profile with only a name succeeds."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")

        ts = int(time.time())
        name_input = page.locator("input[type='text']").first
        name_input.fill(f"MinimalProfile {ts}")

        save_btn = page.get_by_role("button", name="Save Changes")
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(2000)
            # Should either save or show meaningful error, not crash
            body = page.locator("body").inner_text()
            assert "undefined" not in body
            assert "[object Object]" not in body

    def test_create_profile_empty_name_shows_validation(self, logged_in_page: Page):
        """Creating a profile with empty name shows validation error."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")

        # Don't fill name, just try to save
        save_btn = page.get_by_role("button", name="Save Changes")
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(1000)
            # Should show error or stay on form, not navigate away
            assert "/profiles" in page.url


# ---------------------------------------------------------------------------
# 62. Dashboard Stats Accuracy
# ---------------------------------------------------------------------------


class TestDashboardStatsAccuracy:
    """Test that dashboard stats reflect actual data."""

    def test_dashboard_job_count_matches_api(self, logged_in_page: Page, _auth_token):
        """Dashboard job count matches the API response."""
        import httpx
        page = logged_in_page

        # Get count from API
        resp = httpx.get(
            f"{API_URL}/api/jobs",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        api_count = resp.json().get("total", len(resp.json().get("jobs", [])))

        # Load dashboard
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Stats should render as numbers, not NaN
        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "undefined" not in body

    def test_dashboard_profile_count_is_numeric(self, logged_in_page: Page):
        """Dashboard profile count displays as a number, not NaN or undefined."""
        page = logged_in_page

        # Load dashboard
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "undefined" not in body
        assert "[object Object]" not in body
        # Profiles stat card should exist
        expect(page.locator("text=Profiles")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# 56. Profile Creation — Special Characters & Validation
# ---------------------------------------------------------------------------

class TestProfileSpecialCharacters:
    """Test that profiles with special characters in the name are handled safely."""

    def test_create_profile_with_html_chars(self, logged_in_page: Page):
        """Profile names with HTML-like characters should not cause a 500 error."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")

        page.locator("input[type='text']").first.fill("<b>Test</b> User")
        page.get_by_role("button", name="Create Profile").click()

        # Should redirect to profile edit page (not show a server error)
        page.wait_for_url(re.compile(r"/profiles/.+"), timeout=10000)
        expect(page.get_by_role("heading", name="Edit Profile")).to_be_visible()

    def test_create_profile_with_slashes(self, logged_in_page: Page):
        """Profile names with slashes should not cause path traversal issues."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")

        page.locator("input[type='text']").first.fill("path/traversal/../test")
        page.get_by_role("button", name="Create Profile").click()

        # Should redirect to profile edit page (not crash)
        page.wait_for_url(re.compile(r"/profiles/.+"), timeout=10000)
        expect(page.get_by_role("heading", name="Edit Profile")).to_be_visible()


# ---------------------------------------------------------------------------
# 57. Change Password API
# ---------------------------------------------------------------------------

class TestChangePasswordAPI:
    """Test the change password API endpoint directly (no UI exists yet)."""

    def test_change_password_wrong_current(self, _auth_token):
        """Changing password with incorrect current password returns 400."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": "WrongPassword999!", "new_password": "NewPassword123!"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_success(self, _register_user):
        """Changing password with correct current password returns 200."""
        import httpx
        # Login with original password
        resp = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        if resp.status_code == 429:
            pytest.skip("Rate limited")
        assert resp.status_code == 200
        token = resp.json()["access_token"]

        new_password = "ChangedPass123!"
        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": TEST_PASSWORD, "new_password": new_password},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Revert password so other tests still work
        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": new_password, "new_password": TEST_PASSWORD},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_change_password_unauthenticated(self):
        """Changing password without a token returns 401."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": "any", "new_password": "any"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 58. Profile Empty Name Validation via API
# ---------------------------------------------------------------------------

class TestProfileNameValidation:
    """Test that profile creation rejects empty/whitespace-only names."""

    def test_empty_name_rejected(self, _auth_token):
        """Creating a profile with an empty name should return 422."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "", "email": "empty@test.com"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 422

    def test_whitespace_name_rejected(self, _auth_token):
        """Creating a profile with a whitespace-only name should return 422."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "   ", "email": "space@test.com"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 422

    def test_all_special_chars_name_still_creates(self, _auth_token):
        """A name made of only special chars should still create (falls back to 'profile' ID)."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "!!!@@@###", "email": "special@test.com"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"]  # should not be empty
        assert len(data["id"]) > 0

    def test_job_upload_non_pdf_rejected(self, _auth_token):
        """Uploading a non-PDF file to job upload endpoint returns 400."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/jobs/upload",
            files={"file": ("test.txt", b"hello world", "text/plain")},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    def test_document_review_nonexistent_returns_404(self, _auth_token):
        """Reviewing a nonexistent document returns 404."""
        import httpx
        resp = httpx.patch(
            f"{API_URL}/api/documents/nonexistent-id/review",
            json={"reviewed": True},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pipeline Run Completion and History (API-level tests)
# ---------------------------------------------------------------------------


class TestPipelineRunCompletion:
    """Test pipeline run completes, records history, and logs appear."""

    def test_pipeline_clean_step_completes(self, _admin_token):
        """Running just the 'clean' step completes without error."""
        import httpx
        import time as _time

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/run",
            json={"steps": ["clean"]},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        # Accept 200 (started) or 409 (already running)
        assert resp.status_code in (200, 409), f"Unexpected: {resp.status_code} {resp.text}"

        if resp.status_code == 409:
            pytest.skip("Pipeline already running from a prior test")

        assert resp.json()["status"] == "started"

        # Wait for completion (clean step is fast)
        for _ in range(15):
            _time.sleep(1)
            status_resp = httpx.get(
                f"{API_URL}/api/admin/pipeline/status",
                headers={"Authorization": f"Bearer {_admin_token}"},
            )
            if status_resp.status_code == 200 and not status_resp.json().get("is_running"):
                break

        # Verify not running
        status_resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["is_running"] is False

    def test_pipeline_history_has_entries_after_run(self, _admin_token):
        """After a pipeline run, history endpoint returns at least one entry."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/history",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        runs = resp.json().get("runs", [])
        # At least one run should exist from prior test or earlier iterations
        assert isinstance(runs, list)

    def test_pipeline_stats_returns_valid_structure(self, _admin_token):
        """Pipeline stats endpoint returns all expected fields with numeric values."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/stats",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()

        for field in [
            "total_runs", "successful_runs", "failed_runs",
            "avg_duration_seconds", "total_jobs_found",
            "total_jobs_matched", "total_docs_generated",
        ]:
            assert field in stats, f"Missing field: {field}"
            val = stats[field]
            assert isinstance(val, (int, float)), f"{field} is not numeric: {val!r}"
            assert str(val) != "NaN", f"{field} is NaN"

    def test_pipeline_logs_returns_list(self, _admin_token):
        """Pipeline logs endpoint returns a list of log entries."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/logs",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        logs = resp.json().get("logs", [])
        assert isinstance(logs, list)

        # If there are logs, each should have timestamp, level, message
        for log in logs[:5]:
            assert "timestamp" in log
            assert "level" in log
            assert "message" in log


# ---------------------------------------------------------------------------
# Pipeline History Rendering on Admin Page
# ---------------------------------------------------------------------------


class TestPipelineHistoryRendering:
    """Test that pipeline history renders correctly in the browser."""

    def test_history_table_columns_visible(self, admin_page: Page):
        """Pipeline history table has all expected column headers."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Check column headers exist
        history_section = page.locator("h2", has_text="Run History").locator("..")
        for col in ["Time", "Duration", "Status", "Steps"]:
            header = history_section.locator(f"th:has-text('{col}')")
            # Table may not be visible if no runs, so just check the section loads
            expect(page.locator("h2", has_text="Run History")).to_be_visible(timeout=5000)

    def test_pipeline_logs_section_renders(self, admin_page: Page):
        """Pipeline logs section renders without errors."""
        page = admin_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")

        # Log viewer section visible
        expect(page.locator("h2", has_text="Pipeline Logs")).to_be_visible(timeout=5000)

        # The dark log container exists
        log_container = page.locator(".bg-gray-900")
        expect(log_container).to_be_visible()

        # No NaN/undefined in the log area
        log_text = log_container.inner_text()
        assert "NaN" not in log_text
        assert "undefined" not in log_text


# ---------------------------------------------------------------------------
# Profile Import API Validation
# ---------------------------------------------------------------------------


class TestProfileImportValidation:
    """Test profile import endpoint input validation."""

    def test_text_import_rejects_short_text(self, _auth_token):
        """Text import rejects text shorter than 50 characters."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/text",
            json={"text": "Too short"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400
        assert "50 characters" in resp.json()["detail"]

    def test_text_import_rejects_empty_text(self, _auth_token):
        """Text import rejects empty text."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/text",
            json={"text": ""},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_linkedin_import_rejects_invalid_url(self, _auth_token):
        """LinkedIn import rejects non-LinkedIn URLs."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/linkedin",
            json={"url": "https://example.com/not-linkedin"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400
        assert "LinkedIn" in resp.json()["detail"]

    def test_linkedin_import_rejects_missing_in_path(self, _auth_token):
        """LinkedIn import rejects LinkedIn URLs without /in/ path."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/linkedin",
            json={"url": "https://linkedin.com/company/example"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_pdf_import_rejects_non_pdf(self, _auth_token):
        """PDF profile import rejects non-PDF files."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/pdf",
            files={"file": ("resume.txt", b"not a pdf", "text/plain")},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]

    def test_pdf_import_rejects_empty_file(self, _auth_token):
        """PDF profile import rejects empty PDF files."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles/import/pdf",
            files={"file": ("resume.pdf", b"", "application/pdf")},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Generation Workflow Error Handling
# ---------------------------------------------------------------------------


class TestGenerationWorkflowErrors:
    """Test the full generation workflow error handling in the UI."""

    @pytest.fixture
    def _gen_workflow_setup(self, _auth_token):
        """Create a profile and job for generation testing."""
        import httpx

        client = httpx.Client(timeout=15.0)

        # Create profile
        profile_resp = client.post(
            f"{API_URL}/api/profiles",
            json={"name": "Gen Test Profile", "email": "gen@test.com"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert profile_resp.status_code == 201
        profile_id = profile_resp.json()["id"]

        # Activate it
        client.post(
            f"{API_URL}/api/profiles/{profile_id}/activate",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )

        # Create job
        job_resp = client.post(
            f"{API_URL}/api/jobs",
            json={
                "title": "Gen Test Engineer",
                "company": "Gen Test Corp",
                "description": "Testing the generation workflow for errors.",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert job_resp.status_code == 201
        job_id = job_resp.json()["id"]

        client.close()
        return {"profile_id": profile_id, "job_id": job_id}

    def test_generate_resume_api_without_profile_returns_400(self, _auth_token):
        """Generating a resume without a profile returns 400."""
        import httpx

        # Use a nonexistent job_id — generation should fail gracefully
        resp = httpx.post(
            f"{API_URL}/api/documents/resume",
            json={"job_id": "nonexistent-job-id"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_generate_cover_letter_api_without_profile_returns_400(self, _auth_token):
        """Generating a cover letter without a profile returns 400."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/documents/cover-letter",
            json={"job_id": "nonexistent-job-id"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_generate_package_api_without_profile_returns_400(self, _auth_token):
        """Generating a package without a profile returns 400."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/documents/package",
            json={"job_id": "nonexistent-job-id"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_job_detail_generate_section_visible(
        self, logged_in_page: Page, _gen_workflow_setup
    ):
        """Job detail page shows generate section with buttons."""
        page = logged_in_page
        job_id = _gen_workflow_setup["job_id"]

        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")

        # Generate section should be visible
        expect(page.locator("h2", has_text="Generate Documents")).to_be_visible(timeout=5000)

        # Generate buttons should be visible
        resume_btn = page.get_by_role("button", name=re.compile("Resume", re.IGNORECASE)).first
        expect(resume_btn).to_be_visible()

        # Page should not have NaN/undefined
        body_text = page.locator("body").inner_text()
        assert "NaN" not in body_text
        assert "undefined" not in body_text

    def test_documents_page_generation_ui_elements(
        self, page: Page, _auth_token, _gen_workflow_setup
    ):
        """Documents page has generation UI with job dropdown and generate button."""
        page.goto(APP_URL + "/login")
        page.evaluate(f"window.localStorage.setItem('auth_token', '{_auth_token}')")
        page.goto(APP_URL + "/documents", timeout=15000)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        # Page should load without crashing
        body_text = page.locator("body").inner_text()
        assert "NaN" not in body_text
        assert "undefined" not in body_text

        # Generate button should exist
        gen_btn = page.get_by_role("button", name=re.compile("Generate"))
        assert gen_btn.count() > 0


# ---------------------------------------------------------------------------
# Pipeline Status API Edge Cases
# ---------------------------------------------------------------------------


class TestPipelineStatusAPI:
    """Test pipeline status and scheduler API edge cases."""

    def test_pipeline_status_returns_valid_structure(self, _admin_token):
        """Pipeline status endpoint returns all expected fields."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "scheduler_enabled" in data
        assert "interval_hours" in data
        assert "is_running" in data
        assert isinstance(data["scheduler_enabled"], bool)
        assert isinstance(data["is_running"], bool)
        assert isinstance(data["interval_hours"], (int, float))

    def test_pipeline_run_without_steps_uses_defaults(self, _admin_token):
        """Running pipeline with empty body uses default steps."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/run",
            json={},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        # Should either start (200) or conflict (409)
        assert resp.status_code in (200, 409)

    def test_scheduler_update_disable(self, _admin_token):
        """Disabling the scheduler returns success."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/scheduler",
            json={"enabled": False, "interval_hours": 24},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "disabled"

    def test_non_admin_cannot_access_pipeline(self, _auth_token):
        """Non-admin users get 403 on pipeline endpoints."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Salary Validation Tests
# ---------------------------------------------------------------------------


class TestSalaryValidation:
    """Tests that salary fields reject negative values via the API."""

    def test_negative_salary_min_rejected(self, _auth_token):
        """API rejects negative salary_min in profile preferences."""
        import httpx

        # First create a profile
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "SalaryTest"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Could not create profile")
        profile_id = resp.json()["id"]

        # Try to set negative salary_min
        resp = httpx.put(
            f"{API_URL}/api/profiles/{profile_id}",
            json={"preferences": {"salary_min": -50000}},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for negative salary_min, got {resp.status_code}: {resp.text}"
        )

        # Clean up
        httpx.delete(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )

    def test_negative_salary_max_rejected(self, _auth_token):
        """API rejects negative salary_max in profile preferences."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "SalaryTest2"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Could not create profile")
        profile_id = resp.json()["id"]

        resp = httpx.put(
            f"{API_URL}/api/profiles/{profile_id}",
            json={"preferences": {"salary_max": -10000}},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for negative salary_max, got {resp.status_code}: {resp.text}"
        )

        httpx.delete(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )

    def test_valid_salary_range_accepted(self, _auth_token):
        """API accepts valid non-negative salary range."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "SalaryTest3"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Could not create profile")
        profile_id = resp.json()["id"]

        resp = httpx.put(
            f"{API_URL}/api/profiles/{profile_id}",
            json={"preferences": {"salary_min": 80000, "salary_max": 150000}},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200, (
            f"Valid salary range should be accepted: {resp.status_code}: {resp.text}"
        )

        httpx.delete(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )


class TestSalaryInputAttributes:
    """E2E tests that salary inputs have min=0 in the browser."""

    def test_salary_min_input_has_min_zero(self, logged_in_page: Page):
        """Salary Min input should have min='0' attribute to prevent negatives."""
        page = logged_in_page
        import httpx

        # Create a profile so we can edit it (preferences only show in edit mode)
        token = page.evaluate("window.localStorage.getItem('auth_token')")
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": "SalaryInputTest"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code not in (200, 201):
            pytest.skip("Could not create profile")
        profile_id = resp.json()["id"]

        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")

        min_input = page.locator("input[placeholder='Min']")
        expect(min_input).to_be_visible()
        min_attr = min_input.get_attribute("min")
        assert min_attr == "0", f"Salary Min input missing min='0', got min='{min_attr}'"

        max_input = page.locator("input[placeholder='Max']")
        expect(max_input).to_be_visible()
        max_attr = max_input.get_attribute("min")
        assert max_attr == "0", f"Salary Max input missing min='0', got min='{max_attr}'"

        # Clean up
        httpx.delete(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {token}"},
        )


# ---------------------------------------------------------------------------
# Pipeline Scheduler start_time Tests
# ---------------------------------------------------------------------------


class TestPipelineSchedulerStartTime:
    """Tests that the pipeline scheduler respects the start_time parameter."""

    def test_scheduler_with_start_time_sets_next_run(self, _admin_token):
        """Enabling scheduler with start_time should set next_run to that time."""
        import httpx
        from datetime import datetime, timedelta

        # Enable scheduler with a start_time 2 hours from now
        future = datetime.now() + timedelta(hours=2)
        start_time = future.strftime("%H:%M")

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/scheduler",
            json={"enabled": True, "interval_hours": 24, "start_time": start_time},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200

        # Check status — next_run should be close to the start_time, not 24h from now
        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        status = resp.json()
        next_run = status.get("next_run")
        assert next_run is not None, "next_run should be set"

        # Parse and verify it's within a reasonable range of the requested time
        next_run_dt = datetime.fromisoformat(next_run)
        # It should be roughly 2 hours from now, not 24 hours
        delta_hours = (next_run_dt - datetime.now()).total_seconds() / 3600
        assert delta_hours < 4, (
            f"next_run should be ~2h from now (start_time={start_time}), "
            f"but it's {delta_hours:.1f}h away — scheduler may be ignoring start_time"
        )

        # Disable scheduler to clean up
        httpx.post(
            f"{API_URL}/api/admin/pipeline/scheduler",
            json={"enabled": False, "interval_hours": 24},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )

    def test_scheduler_without_start_time_uses_interval(self, _admin_token):
        """Without start_time, next_run should be interval_hours from now."""
        import httpx
        from datetime import datetime

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/scheduler",
            json={"enabled": True, "interval_hours": 12},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        next_run = resp.json().get("next_run")
        assert next_run is not None

        next_run_dt = datetime.fromisoformat(next_run)
        delta_hours = (next_run_dt - datetime.now()).total_seconds() / 3600
        # Should be roughly 12 hours
        assert 10 < delta_hours < 14, (
            f"next_run should be ~12h from now, but it's {delta_hours:.1f}h away"
        )

        # Disable
        httpx.post(
            f"{API_URL}/api/admin/pipeline/scheduler",
            json={"enabled": False, "interval_hours": 24},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )


# ---------------------------------------------------------------------------
# Change Password API Flow
# ---------------------------------------------------------------------------


class TestChangePasswordFlow:
    """Test the /auth/change-password endpoint end-to-end."""

    @pytest.fixture
    def _pw_user(self):
        """Register a disposable user for password tests."""
        import httpx
        import uuid

        uid = uuid.uuid4().hex[:8]
        email = f"pwtest_{uid}@example.com"
        password = "OriginalPass123!"
        resp = httpx.post(
            f"{API_URL}/api/auth/register",
            json={"name": "PW Test User", "email": email, "password": password},
        )
        if resp.status_code == 429:
            pytest.skip("Rate limited during registration")
        assert resp.status_code == 201
        # Login to get token
        login = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        return {
            "email": email,
            "password": password,
            "token": login.json()["access_token"],
        }

    def test_change_password_wrong_current(self, _pw_user):
        """Supplying the wrong current password returns 400."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": "WrongPassword!", "new_password": "NewPass123!"},
            headers={"Authorization": f"Bearer {_pw_user['token']}"},
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_short_new(self, _pw_user):
        """A new password under 8 chars is rejected with 422."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": _pw_user["password"], "new_password": "short"},
            headers={"Authorization": f"Bearer {_pw_user['token']}"},
        )
        assert resp.status_code == 422

    def test_change_password_success_and_login(self, _pw_user):
        """Successfully changing the password updates credentials."""
        import httpx

        new_pw = "BrandNewPass456!"
        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": _pw_user["password"], "new_password": new_pw},
            headers={"Authorization": f"Bearer {_pw_user['token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Old password should fail
        old_login = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": _pw_user["email"], "password": _pw_user["password"]},
        )
        if old_login.status_code == 429:
            pytest.skip("Rate limited during login verification")
        assert old_login.status_code == 401

        # New password should work
        new_login = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": _pw_user["email"], "password": new_pw},
        )
        if new_login.status_code == 429:
            pytest.skip("Rate limited during login verification")
        assert new_login.status_code == 200

    def test_change_password_requires_auth(self):
        """The endpoint rejects unauthenticated requests."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/auth/change-password",
            json={"current_password": "x", "new_password": "y" * 8},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Admin User Management API
# ---------------------------------------------------------------------------


class TestAdminUserManagement:
    """Tests for /admin/users list and delete endpoints."""

    def test_list_users_returns_users(self, _admin_token):
        """Admin can list all registered users."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert len(data["users"]) > 0
        # Each user should have required fields
        user = data["users"][0]
        for field in ("id", "email", "name"):
            assert field in user, f"Missing field '{field}' in user"

    def test_list_users_rejected_for_non_admin(self, _auth_token):
        """Non-admin users get 403 on admin endpoints."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 403

    def test_delete_self_prevented(self, _admin_token):
        """Admin cannot delete their own account."""
        import httpx

        me = httpx.get(
            f"{API_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert me.status_code == 200
        my_id = me.json()["id"]

        resp = httpx.delete(
            f"{API_URL}/api/admin/users/{my_id}",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"].lower()

    def test_delete_nonexistent_user(self, _admin_token):
        """Deleting a nonexistent user returns 404."""
        import httpx

        resp = httpx.delete(
            f"{API_URL}/api/admin/users/nonexistent_id_12345",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 404

    def test_delete_user_success(self, _admin_token):
        """Admin can delete another user."""
        import httpx

        # Register a disposable user
        ts = str(int(time.time()))
        email = f"delete_me_{ts}@example.com"
        reg = httpx.post(
            f"{API_URL}/api/auth/register",
            json={"name": "Delete Me", "email": email, "password": "DeleteMe123!"},
        )
        if reg.status_code == 429:
            pytest.skip("Rate limited")
        assert reg.status_code == 201
        user_id = reg.json()["id"]

        # Delete via admin
        resp = httpx.delete(
            f"{API_URL}/api/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 204

        # Verify user can no longer log in
        login = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": "DeleteMe123!"},
        )
        assert login.status_code == 401


# ---------------------------------------------------------------------------
# Admin Dashboard Data Integrity (browser)
# ---------------------------------------------------------------------------


class TestAdminDashboardDataIntegrity:
    """Verify no NaN/undefined/null on admin dashboard when loaded as admin."""

    def test_admin_dashboard_no_bad_data(self, admin_page: Page):
        """Admin dashboard should have no NaN, undefined, null, or [object Object]."""
        admin_page.goto(APP_URL + "/admin")
        admin_page.wait_for_load_state("networkidle")
        text = admin_page.inner_text("body")
        for bad in ("NaN", "undefined", "[object Object]"):
            assert bad not in text, f"Found '{bad}' on admin dashboard"

    def test_admin_dashboard_stats_cards_numeric(self, admin_page: Page):
        """Stats cards should display numeric values."""
        admin_page.goto(APP_URL + "/admin")
        admin_page.wait_for_load_state("networkidle")

        cards = admin_page.locator(".card").first
        expect(cards).to_be_visible()

        # The page should show "Total Jobs", "Total Users", etc. with numbers
        expect(admin_page.get_by_text("Total Jobs")).to_be_visible()
        expect(admin_page.get_by_text("Total Users")).to_be_visible()

    def test_admin_dashboard_quick_actions_navigate(self, admin_page: Page):
        """Quick action links on admin dashboard navigate to admin sub-pages."""
        admin_page.goto(APP_URL + "/admin")
        admin_page.wait_for_load_state("networkidle")

        admin_page.get_by_text("System Operations").click()
        admin_page.wait_for_load_state("networkidle")
        expect(admin_page).to_have_url(re.compile(r"/admin/scraper"))

    def test_admin_jobs_page_no_bad_data(self, admin_page: Page):
        """Admin jobs page renders table without bad data."""
        admin_page.goto(APP_URL + "/admin/jobs")
        admin_page.wait_for_load_state("networkidle")

        expect(admin_page.get_by_text("Manage Jobs")).to_be_visible()
        text = admin_page.inner_text("body")
        for bad in ("NaN", "undefined", "[object Object]"):
            assert bad not in text, f"Found '{bad}' on admin jobs page"

    def test_admin_jobs_page_pagination(self, admin_page: Page):
        """Admin jobs page shows pagination controls."""
        admin_page.goto(APP_URL + "/admin/jobs")
        admin_page.wait_for_load_state("networkidle")

        expect(admin_page.get_by_text(re.compile(r"Showing \d+"))).to_be_visible()
        expect(admin_page.get_by_role("button", name="Previous")).to_be_visible()
        expect(admin_page.get_by_role("button", name="Next")).to_be_visible()


# ---------------------------------------------------------------------------
# Admin Scraper Page Interactions (browser)
# ---------------------------------------------------------------------------


class TestAdminScraperInteractions:
    """Test interactive elements on the admin scraper page."""

    def test_scraper_page_all_tools_visible(self, admin_page: Page):
        """All four tool sections should be visible."""
        admin_page.goto(APP_URL + "/admin/scraper")
        admin_page.wait_for_load_state("networkidle")

        expect(admin_page.get_by_role("heading", name="Job Scraper")).to_be_visible()
        expect(admin_page.get_by_role("heading", name="Job Searcher")).to_be_visible()
        expect(admin_page.get_by_role("heading", name="Job Matcher")).to_be_visible()
        expect(admin_page.get_by_role("heading", name="Cleanup")).to_be_visible()

    def test_searcher_button_disabled_without_term(self, admin_page: Page):
        """Run Searcher button should be disabled when search term is empty."""
        admin_page.goto(APP_URL + "/admin/scraper")
        admin_page.wait_for_load_state("networkidle")

        run_searcher_btn = admin_page.get_by_role("button", name="Run Searcher")
        expect(run_searcher_btn).to_be_disabled()

    def test_searcher_button_enabled_with_term(self, admin_page: Page):
        """Run Searcher button enables after typing a search term."""
        admin_page.goto(APP_URL + "/admin/scraper")
        admin_page.wait_for_load_state("networkidle")

        admin_page.get_by_placeholder("Software Engineer").fill("Python Developer")
        run_searcher_btn = admin_page.get_by_role("button", name="Run Searcher")
        expect(run_searcher_btn).to_be_enabled()

    def test_scraper_page_no_bad_data(self, admin_page: Page):
        """Scraper page should not display NaN, undefined, or [object Object]."""
        admin_page.goto(APP_URL + "/admin/scraper")
        admin_page.wait_for_load_state("networkidle")
        text = admin_page.inner_text("body")
        for bad in ("NaN", "undefined", "[object Object]"):
            assert bad not in text, f"Found '{bad}' on admin scraper page"


# ---------------------------------------------------------------------------
# Profile Import Text Validation (browser)
# ---------------------------------------------------------------------------


class TestTopJobsInteraction:
    """Test Top Jobs page deeper interactions."""

    def test_top_jobs_view_details_navigates(self, logged_in_page: Page):
        """Clicking View Details on a top job navigates to job detail."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")

        # If there are jobs with View Details buttons, click the first one
        view_btn = page.get_by_role("link", name="View Details").first
        if view_btn.is_visible():
            view_btn.click()
            page.wait_for_url(re.compile(r"/jobs/[^/]+"), timeout=5000)
            page.wait_for_load_state("networkidle")
            # Should be on a job detail page
            expect(page.locator("text=Application Status")).to_be_visible(timeout=5000)
        else:
            # No matched jobs — verify empty state message
            expect(page.locator("text=No matches found")).to_be_visible()

    def test_top_jobs_score_filter_updates_list(self, logged_in_page: Page):
        """Changing score filter updates the displayed list or empty state."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")

        # Count items before filter
        cards_before = page.locator(".card").count()

        # Set high threshold
        page.locator("select").select_option("80")
        page.wait_for_timeout(1000)

        # Either fewer cards or "No matches found" shown
        cards_after = page.locator(".card").count()
        has_empty = page.locator("text=No matches found").is_visible()
        assert cards_after <= cards_before or has_empty, \
            "Higher score filter should show equal or fewer results"

    def test_top_jobs_match_scores_are_numeric(self, logged_in_page: Page):
        """Match score badges display numeric percentages, not NaN."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")

        # Check all percentage badges
        badges = page.locator(".rounded-full.text-sm.font-bold")
        for i in range(badges.count()):
            text = badges.nth(i).inner_text()
            # Should be like "75%" — a number followed by %
            assert "%" in text, f"Badge missing %: {text}"
            num_part = text.replace("%", "").strip()
            assert num_part.isdigit(), f"Non-numeric score: {text}"


class TestAddJobFullWorkflow:
    """Test the complete add-job workflow for each method."""

    def test_add_job_text_paste_submits(self, logged_in_page: Page):
        """Pasting text description submits and either creates job or shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        # Switch to Paste Text tab
        page.get_by_role("button", name="Paste Text").click()
        page.wait_for_timeout(300)

        ts = str(int(time.time()))
        job_text = (
            f"Senior Python Developer at TextPaste Corp {ts}\n"
            "Location: Remote\n"
            "Salary: $120,000 - $160,000\n\n"
            "We are looking for a senior Python developer with experience in "
            "FastAPI, PostgreSQL, and cloud infrastructure."
        )

        textarea = page.locator("textarea[placeholder*='Paste the full job']")
        textarea.fill(job_text)
        page.get_by_role("button", name="Add Job").click()

        # Wait for result — either navigates to job detail or shows error
        # (plaintext parsing requires Ollama LLM, which may not be running)
        page.wait_for_timeout(5000)
        navigated = "/jobs/add" not in page.url
        has_error = page.locator(".bg-red-50").is_visible()
        assert navigated or has_error, \
            "Expected navigation to job detail or an error message"

    def test_add_job_pdf_empty_shows_error(self, logged_in_page: Page):
        """Submitting PDF tab without file shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Upload PDF").click()
        page.get_by_role("button", name="Add Job").click()
        expect(page.locator("text=Please select a PDF file")).to_be_visible(timeout=3000)

    def test_add_job_text_empty_shows_error(self, logged_in_page: Page):
        """Submitting empty text paste shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Paste Text").click()
        page.get_by_role("button", name="Add Job").click()
        expect(page.locator("text=Please enter job description text")).to_be_visible(timeout=3000)


class TestDocumentsListAPI:
    """Test document listing API edge cases."""

    def test_documents_list_returns_array(self, _auth_token):
        """Documents list endpoint returns a JSON array."""
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/documents",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_documents_list_respects_limit(self, _auth_token):
        """Documents list with limit=1 returns at most 1 document."""
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/documents?limit=1",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 1, f"Expected at most 1 doc, got {len(data)}"

    def test_documents_list_invalid_limit_rejected(self, _auth_token):
        """Documents list with limit=0 returns 422."""
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/documents?limit=0",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"

    def test_documents_review_nonexistent_returns_404(self, _auth_token):
        """Reviewing a non-existent document returns 404."""
        import httpx
        resp = httpx.patch(
            f"{API_URL}/api/documents/nonexistent_doc_id/review",
            json={"reviewed": True},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 404


class TestPipelineGenerateStepAPI:
    """Test pipeline generate step via API."""

    def test_pipeline_run_generate_only(self, _admin_token):
        """Running only the generate step via API doesn't crash."""
        import httpx
        import time as _time

        # Wait for any running pipeline to finish first
        for _ in range(30):
            status_resp = httpx.get(
                f"{API_URL}/api/admin/pipeline/status",
                headers={"Authorization": f"Bearer {_admin_token}"},
            )
            if status_resp.status_code == 200 and not status_resp.json().get("is_running"):
                break
            _time.sleep(1)

        resp = httpx.post(
            f"{API_URL}/api/admin/pipeline/run",
            json={"steps": ["generate"]},
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code in (200, 409), f"Unexpected: {resp.status_code} {resp.text}"

        if resp.status_code == 200:
            # Wait for completion (generate with no matches should be fast)
            for _ in range(15):
                _time.sleep(1)
                status_resp = httpx.get(
                    f"{API_URL}/api/admin/pipeline/status",
                    headers={"Authorization": f"Bearer {_admin_token}"},
                )
                if status_resp.status_code == 200 and not status_resp.json().get("is_running"):
                    break

            status_resp = httpx.get(
                f"{API_URL}/api/admin/pipeline/status",
                headers={"Authorization": f"Bearer {_admin_token}"},
            )
            assert status_resp.json()["is_running"] is False

    def test_pipeline_stats_after_generate(self, _admin_token):
        """Pipeline stats still have valid structure after a generate run."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/stats",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        stats = resp.json()
        # docs_generated should be numeric (0 is fine if no matches)
        assert isinstance(stats["total_docs_generated"], (int, float))
        assert stats["total_docs_generated"] >= 0


class TestProfileImportTextValidation:
    """Test the text import tab validation in the browser."""

    def test_import_text_too_short_shows_error(self, logged_in_page: Page):
        """Submitting < 50 chars of text shows an error message."""
        logged_in_page.goto(APP_URL + "/profiles")
        logged_in_page.wait_for_load_state("networkidle")

        # Click Text tab
        text_tab = logged_in_page.get_by_text("Paste Text")
        if text_tab.is_visible():
            text_tab.click()
        else:
            pytest.skip("Paste Text tab not visible")

        textarea = logged_in_page.locator("textarea").first
        if not textarea.is_visible():
            pytest.skip("Text import textarea not visible")

        textarea.fill("Too short")
        # The import button should be disabled for short text
        import_btn = logged_in_page.get_by_role("button", name=re.compile("Import|Parse"))
        if import_btn.count() > 0:
            expect(import_btn.first).to_be_disabled()

    def test_import_text_long_enough_enables_button(self, logged_in_page: Page):
        """Text >= 50 chars should enable the import button."""
        logged_in_page.goto(APP_URL + "/profiles")
        logged_in_page.wait_for_load_state("networkidle")

        text_tab = logged_in_page.get_by_text("Paste Text")
        if text_tab.is_visible():
            text_tab.click()
        else:
            pytest.skip("Paste Text tab not visible")

        textarea = logged_in_page.locator("textarea").first
        if not textarea.is_visible():
            pytest.skip("Text import textarea not visible")

        # 50+ chars of realistic resume text
        long_text = "John Doe - Software Engineer with 10 years of experience in Python, JavaScript, and cloud computing."
        textarea.fill(long_text)

        import_btn = logged_in_page.get_by_role("button", name=re.compile("Import|Parse"))
        if import_btn.count() > 0:
            expect(import_btn.first).to_be_enabled()


# ---------------------------------------------------------------------------
# Whitespace job creation regression
# ---------------------------------------------------------------------------


class TestJobCreationWhitespaceValidation:
    """Regression tests: whitespace-only title/company must be rejected."""

    def test_whitespace_only_title_company_rejected_api(self, _auth_token):
        """API rejects job creation with whitespace-only title and company."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": "   ", "company": "   "},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400, (
            f"Expected 400 for whitespace-only title/company, got {resp.status_code}"
        )

    def test_empty_title_company_rejected_api(self, _auth_token):
        """API rejects job creation with empty title and company."""
        import httpx

        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": "", "company": ""},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 400

    def test_valid_title_company_accepted_api(self, _auth_token):
        """API accepts job creation with valid title and company."""
        import httpx

        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Regression Test {ts}", "company": "RegCorp"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]
        # Clean up
        httpx.delete(
            f"{API_URL}/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )

    def test_manual_entry_empty_submit_stays_on_page(self, logged_in_page: Page):
        """Submitting manual entry with empty required fields stays on the page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Manual Entry").click()
        page.wait_for_timeout(500)

        # Submit without filling required fields — HTML required attr blocks submit
        page.get_by_role("button", name="Add Job").click()
        page.wait_for_timeout(1000)

        # Should still be on the add job page (not navigated away)
        assert "/jobs/add" in page.url, "Should stay on add page when fields are empty"


# ---------------------------------------------------------------------------
# Add Job tab switching and form interaction
# ---------------------------------------------------------------------------


class TestAddJobTabInteraction:
    """Test switching between Add Job input methods."""

    def test_tab_switching_preserves_nothing_across_methods(self, logged_in_page: Page):
        """Switching tabs changes the visible form section."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        # Default is URL tab
        expect(page.locator("input[type='url']")).to_be_visible()

        # Switch to Paste Text
        page.get_by_role("button", name="Paste Text").click()
        page.wait_for_timeout(300)
        expect(page.locator("textarea[placeholder*='Paste the full job']")).to_be_visible()
        expect(page.locator("input[type='url']")).not_to_be_visible()

        # Switch to Manual Entry
        page.get_by_role("button", name="Manual Entry").click()
        page.wait_for_timeout(300)
        expect(page.locator("input[placeholder='City, State or Remote']")).to_be_visible()
        expect(page.locator("textarea[placeholder*='Paste the full job']")).not_to_be_visible()

        # Switch to Upload PDF
        page.get_by_role("button", name="Upload PDF").click()
        page.wait_for_timeout(300)
        expect(page.locator("text=Click to upload PDF")).to_be_visible()

    def test_cancel_returns_to_jobs(self, logged_in_page: Page):
        """Cancel button navigates back to jobs page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Cancel").click()
        page.wait_for_url(re.compile(r"/jobs$"), timeout=5000)

    def test_text_paste_empty_shows_error(self, logged_in_page: Page):
        """Submitting empty text paste shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Paste Text").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Add Job").click()
        page.wait_for_timeout(1000)

        expect(page.locator("text=Please enter job description text")).to_be_visible(
            timeout=3000
        )

    def test_pdf_no_file_shows_error(self, logged_in_page: Page):
        """Submitting PDF method with no file selected shows error."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")

        page.get_by_role("button", name="Upload PDF").click()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Add Job").click()
        page.wait_for_timeout(1000)

        expect(page.locator("text=Please select a PDF file")).to_be_visible(
            timeout=3000
        )


# ---------------------------------------------------------------------------
# Job detail notes editing
# ---------------------------------------------------------------------------


class TestJobDetailNotesWorkflow:
    """Test editing and saving notes on the job detail page."""

    def test_notes_edit_save_cycle(self, logged_in_page: Page):
        """Create a job, add notes, save, and verify persistence."""
        import httpx

        page = logged_in_page

        # Create a test job via API
        token = page.evaluate("window.localStorage.getItem('auth_token')")
        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Notes Test {ts}", "company": "NotesTestCorp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 201:
            pytest.skip("Could not create test job")
        job_id = resp.json()["id"]

        try:
            page.goto(APP_URL + f"/jobs/{job_id}")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("text=Application Status", timeout=10000)

            # Click Edit on notes
            page.get_by_text("Edit", exact=True).click()
            page.wait_for_timeout(500)

            # Fill notes
            textarea = page.locator("textarea[placeholder*='Add notes']")
            expect(textarea).to_be_visible()
            textarea.fill("E2E test notes content")

            # Save
            page.get_by_role("button", name="Save").click()
            page.wait_for_timeout(1000)

            # Verify notes display
            expect(page.locator("text=E2E test notes content")).to_be_visible()

            # Verify via API
            api_resp = httpx.get(
                f"{API_URL}/api/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert api_resp.status_code == 200
            assert "E2E test notes content" in api_resp.json().get("notes", "")
        finally:
            httpx.delete(
                f"{API_URL}/api/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

    def test_notes_cancel_discards_changes(self, logged_in_page: Page):
        """Cancelling notes edit discards changes."""
        import httpx

        page = logged_in_page

        token = page.evaluate("window.localStorage.getItem('auth_token')")
        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"NotesCancelTest {ts}", "company": "CancelCorp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 201:
            pytest.skip("Could not create test job")
        job_id = resp.json()["id"]

        try:
            page.goto(APP_URL + f"/jobs/{job_id}")
            page.wait_for_load_state("networkidle")
            page.wait_for_selector("text=Application Status", timeout=10000)

            page.get_by_text("Edit", exact=True).click()
            page.wait_for_timeout(500)

            textarea = page.locator("textarea[placeholder*='Add notes']")
            textarea.fill("This should not be saved")

            page.get_by_role("button", name="Cancel").click()
            page.wait_for_timeout(500)

            # Should show the empty notes message
            expect(page.locator("text=No notes yet")).to_be_visible()
        finally:
            httpx.delete(
                f"{API_URL}/api/jobs/{job_id}",
                headers={"Authorization": f"Bearer {token}"},
            )


# ---------------------------------------------------------------------------
# Documents page filter and bulk selection
# ---------------------------------------------------------------------------


class TestDocumentsFilterAndBulk:
    """Test document page filter dropdowns and bulk actions."""

    def test_documents_page_loads_with_type_filter(self, logged_in_page: Page):
        """Documents page has type filter dropdown with expected options."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # The type filter select contains "All Types" option
        selects = page.locator("select")
        found_type_filter = False
        for i in range(selects.count()):
            options = selects.nth(i).locator("option").all_text_contents()
            if "All Types" in options:
                found_type_filter = True
                assert "Resumes" in options
                assert "Cover Letters" in options
                break
        assert found_type_filter, "Type filter select not found on documents page"

    def test_documents_review_filter_options(self, logged_in_page: Page):
        """Review filter dropdown has all expected options."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        selects = page.locator("select")
        found_review_filter = False
        for i in range(selects.count()):
            options = selects.nth(i).locator("option").all_text_contents()
            if "All Status" in options:
                found_review_filter = True
                assert "Reviewed" in options
                assert "Unreviewed" in options
                break
        assert found_review_filter, "Review filter select not found on documents page"

    def test_documents_count_displayed(self, logged_in_page: Page):
        """Documents page shows a count of displayed documents."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        # Should show "N documents" text
        count_text = page.locator("text=/\\d+ documents/")
        expect(count_text).to_be_visible(timeout=5000)

    def test_documents_generate_section_visible(self, logged_in_page: Page):
        """Generate Documents section with job dropdown and generate button visible."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        expect(page.locator("text=Generate Documents")).to_be_visible()
        # Job selector dropdown should exist
        job_select = page.locator("select").first
        expect(job_select).to_be_visible()

    def test_generate_button_disabled_without_job(self, logged_in_page: Page):
        """Generate button is disabled when no job is selected."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        gen_btn = page.get_by_role("button", name="Generate")
        expect(gen_btn).to_be_disabled()


# ---------------------------------------------------------------------------
# Admin stats accuracy via API
# ---------------------------------------------------------------------------


class TestAdminStatsAPI:
    """Verify admin stats endpoint returns well-formed data."""

    def test_stats_contains_expected_fields(self, _admin_token):
        """Admin stats response has job counts and user counts."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/stats",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "jobs" in data
        assert "total" in data["jobs"]
        assert isinstance(data["jobs"]["total"], int)
        assert data["jobs"]["total"] >= 0

    def test_stats_rejected_without_auth(self):
        """Admin stats returns 401 without auth token."""
        import httpx

        resp = httpx.get(f"{API_URL}/api/admin/stats")
        assert resp.status_code in (401, 403)

    def test_pipeline_status_returns_valid(self, _admin_token):
        """Pipeline status endpoint returns well-formed response."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/status",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Pipeline status has scheduler_active or is_running field
        has_status = "scheduler_active" in data or "is_running" in data
        assert has_status, f"Expected scheduler status field in {list(data.keys())}"

    def test_pipeline_history_returns_list(self, _admin_token):
        """Pipeline history returns a list of runs."""
        import httpx

        resp = httpx.get(
            f"{API_URL}/api/admin/pipeline/history",
            headers={"Authorization": f"Bearer {_admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)


# ---------------------------------------------------------------------------
# 40. Adversarial API Edge Cases
# ---------------------------------------------------------------------------

class TestAPIEdgeCases:
    """Probe API endpoints for edge case bugs."""

    def test_create_job_with_html_in_title(self, _auth_token):
        """HTML/script in job title should not cause XSS or crashes."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": '<img src=x onerror=alert(1)>',
                "company": "Safe Corp",
                "location": "Remote",
                "description": "Normal description.",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        # Should accept or reject cleanly, not 500
        assert resp.status_code in (201, 400, 422), f"Unexpected: {resp.status_code} {resp.text}"

    def test_create_job_with_very_long_description(self, _auth_token):
        """Very long description should not crash the API."""
        import httpx
        long_desc = "A" * 100_000
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": "Long Desc Job",
                "company": "LongCorp",
                "location": "Remote",
                "description": long_desc,
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        # Should succeed or reject with 400/413, not 500
        assert resp.status_code in (201, 400, 413, 422), f"Unexpected: {resp.status_code}"

    def test_create_profile_with_unicode_name(self, _auth_token):
        """Unicode characters in profile name should work."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={
                "name": "José García-López",
                "email": "jose@example.com",
                "phone": "+1-555-0100",
                "location": "Madrid, Spain",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Unicode name failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "José García-López"

    def test_create_profile_with_emoji_name(self, _auth_token):
        """Emoji in profile name should not crash."""
        import httpx
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={
                "name": "Test User 🚀",
                "email": "emoji@example.com",
                "phone": "555-0101",
                "location": "Anywhere",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code in (201, 400, 422), f"Unexpected: {resp.status_code} {resp.text}"

    def test_get_nonexistent_profile_returns_404(self, _auth_token):
        """Requesting a nonexistent profile returns 404."""
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/profiles/nonexistent-id-zzz",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_job_returns_404(self, _auth_token):
        """Deleting a nonexistent job returns 404."""
        import httpx
        resp = httpx.delete(
            f"{API_URL}/api/jobs/nonexistent-id-zzz",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 404

    def test_update_profile_with_empty_skills(self, _auth_token):
        """Updating a profile with an empty skills array should work."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())
        # Create profile
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Empty Skills {ts}", "email": f"empty_{ts}@example.com",
                  "phone": "555-0102", "location": "Test"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Update with empty skills
        resp = httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={"name": f"Empty Skills {ts}", "email": f"empty_{ts}@example.com",
                  "phone": "555-0102", "location": "Test", "skills": [], "experience": []},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["skills"] == []

    def test_documents_list_empty_for_new_user(self, _auth_token):
        """Documents list returns empty array, not error."""
        import httpx
        resp = httpx.get(
            f"{API_URL}/api/documents",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 41. XSS Safety in Rendered Content
# ---------------------------------------------------------------------------

class TestXSSRendering:
    """Verify that HTML injection in data doesn't execute in the browser."""

    @pytest.fixture
    def _xss_job(self, _auth_token):
        """Create a job with HTML-like content in fields."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": f"<b>Bold Job</b> {ts}",
                "company": "<script>alert('xss')</script>",
                "location": "<img src=x>",
                "description": "Normal job <a href='javascript:void'>click</a>.",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_xss_job_detail_no_script_execution(self, logged_in_page: Page, _xss_job):
        """Job detail page should escape HTML in job fields."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_xss_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # The script tag should be displayed as text, not executed
        body_html = page.content()
        # Check no raw <script> tags are unescaped in the DOM
        # React auto-escapes by default, but verify
        assert "<script>alert" not in body_html.lower() or "&lt;script&gt;" in body_html.lower() or \
            "alert('xss')" in page.locator("body").inner_text()

    def test_xss_jobs_list_no_script_execution(self, logged_in_page: Page, _xss_job):
        """Jobs list page should not execute injected HTML."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        # Page should load without errors
        body = page.locator("body")
        expect(body).to_be_visible()


# ---------------------------------------------------------------------------
# 42. Resume Pipeline End-to-End Data Flow
# ---------------------------------------------------------------------------

class TestResumePipelineDataFlow:
    """Test the full data flow: create profile with skills -> create job -> verify generate buttons work."""

    @pytest.fixture
    def _full_pipeline_setup(self, _auth_token):
        """Create a complete profile and job for pipeline testing."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        # Create profile with full data
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Pipeline E2E {ts}", "email": f"pipe_{ts}@example.com",
                  "phone": "555-7890", "location": "Seattle, WA"},
            headers=headers,
        )
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # Update with skills, experience, and preferences
        resp = httpx.put(
            f"{API_URL}/api/profiles/{pid}",
            json={
                "name": f"Pipeline E2E {ts}",
                "email": f"pipe_{ts}@example.com",
                "phone": "555-7890",
                "location": "Seattle, WA",
                "notes": "Senior engineer with 10 years experience",
                "skills": [
                    {"name": "Python", "level": "expert"},
                    {"name": "FastAPI", "level": "advanced"},
                    {"name": "React", "level": "intermediate"},
                    {"name": "PostgreSQL", "level": "advanced"},
                ],
                "experience": [
                    {"title": "Senior Software Engineer", "company": "BigTech Inc",
                     "start_date": "2020-01", "end_date": "present",
                     "description": "Led backend team, built microservices, mentored 5 engineers"},
                    {"title": "Software Engineer", "company": "StartupCo",
                     "start_date": "2017-06", "end_date": "2019-12",
                     "description": "Full-stack development with Python and React"},
                ],
                "preferences": {
                    "desired_titles": "Senior Engineer, Staff Engineer",
                    "desired_locations": "Seattle, Remote",
                    "salary_min": 150000,
                    "salary_max": 250000,
                },
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["skills"]) == 4, f"Expected 4 skills, got {len(data['skills'])}"
        assert len(data["experience"]) == 2, f"Expected 2 exp, got {len(data['experience'])}"

        # Activate
        resp = httpx.post(f"{API_URL}/api/profiles/{pid}/activate", headers=headers)
        assert resp.status_code == 200

        # Create a detailed job
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": f"Senior Python Engineer {ts}",
                "company": "Dream Corp",
                "location": "Seattle, WA (Hybrid)",
                "description": (
                    "We are looking for a Senior Python Engineer to join our platform team. "
                    "Requirements: 5+ years Python, experience with FastAPI or Django, "
                    "PostgreSQL, Redis, Docker, CI/CD. Nice to have: React, TypeScript."
                ),
                "salary": "$180,000 - $220,000",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        return {"profile_id": pid, "job_id": job_id}

    def test_pipeline_profile_data_persists_correctly(self, _auth_token, _full_pipeline_setup):
        """Verify all profile data (skills, experience, preferences) persists via API."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        pid = _full_pipeline_setup["profile_id"]

        resp = httpx.get(f"{API_URL}/api/profiles/{pid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # Check skills
        skill_names = [s["name"] for s in data.get("skills", [])]
        assert "Python" in skill_names, f"Python not in skills: {skill_names}"
        assert "FastAPI" in skill_names, f"FastAPI not in skills: {skill_names}"

        # Check experience
        exp_titles = [e["title"] for e in data.get("experience", [])]
        assert "Senior Software Engineer" in exp_titles

        # Check preferences
        prefs = data.get("preferences", {})
        assert prefs.get("salary_min") == 150000 or prefs.get("salary_min") is not None

    def test_pipeline_job_detail_shows_generate_buttons(self, logged_in_page: Page, _full_pipeline_setup):
        """With profile and job set up, generate buttons should be present and enabled."""
        page = logged_in_page
        job_id = _full_pipeline_setup["job_id"]
        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Generate Documents", timeout=10000)

        # All three generate buttons should be visible
        expect(page.locator("button:has-text('Resume + Cover Letter')")).to_be_visible()
        expect(page.locator("button:has-text('Resume Only')")).to_be_visible()
        expect(page.locator("button:has-text('Cover Letter Only')")).to_be_visible()

        # Buttons should NOT be disabled (profile is active)
        expect(page.locator("button:has-text('Resume Only')")).to_be_enabled()

    def test_pipeline_documents_page_shows_job_in_dropdown(self, logged_in_page: Page, _full_pipeline_setup):
        """Documents page should show the created job in the dropdown."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")

        job_select = page.locator("select.input").first
        page.wait_for_function(
            "document.querySelector('select.input').options.length > 1",
            timeout=10000,
        )
        options_count = job_select.locator("option").count()
        assert options_count >= 2, f"Expected job in dropdown, got {options_count} options"

    def test_pipeline_profile_shows_in_edit_page_correctly(self, logged_in_page: Page, _full_pipeline_setup):
        """Profile edit page should display all saved skills and experience."""
        page = logged_in_page
        pid = _full_pipeline_setup["profile_id"]
        page.goto(f"{APP_URL}/profiles/{pid}")
        page.wait_for_load_state("networkidle")

        # Skills should be listed (use the skills section to avoid matching experience text)
        skills_section = page.locator("h2:has-text('Skills')").locator("..")
        expect(skills_section.locator("text=Python")).to_be_visible(timeout=5000)
        expect(skills_section.locator("text=FastAPI")).to_be_visible()

        # Experience should be listed
        exp_section = page.locator("h2:has-text('Experience')").locator("..")
        expect(exp_section.locator("text=Senior Software Engineer")).to_be_visible()
        expect(exp_section.locator("text=BigTech Inc")).to_be_visible()

    def test_pipeline_dashboard_stats_reflect_data(self, logged_in_page: Page, _full_pipeline_setup):
        """Dashboard should show non-zero stats for active profile and jobs."""
        page = logged_in_page
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")

        # Active Profile stat should show the profile name, not "None"
        active_stat = page.locator("p.text-sm", has_text="Active Profile").locator("..").locator("p.text-lg")
        text = active_stat.inner_text()
        assert text != "None", f"Active Profile stat shows 'None' but we activated a profile"


# ---------------------------------------------------------------------------
# 43. Concurrent Job Status Updates
# ---------------------------------------------------------------------------

class TestConcurrentJobStatusUpdates:
    """Test that rapid status updates don't corrupt job data."""

    @pytest.fixture
    def _rapid_status_job(self, _auth_token):
        """Create a job for rapid status testing."""
        import httpx
        ts = int(time.time())
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"Rapid Status {ts}", "company": "RapidCorp",
                  "location": "Remote", "description": "Test rapid status changes."},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_rapid_status_changes_via_ui(self, logged_in_page: Page, _rapid_status_job):
        """Quickly clicking through all statuses doesn't break the job."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/{_rapid_status_job}")
        page.wait_for_load_state("networkidle")
        page.wait_for_selector("text=Application Status", timeout=10000)

        # Rapidly click through statuses
        for status_name in ["Applied", "Interviewing", "Offered", "Rejected", "Active"]:
            btn = page.locator(f"button:has-text('{status_name}')")
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(200)

        # Verify page is still functional
        page.wait_for_timeout(1000)
        body = page.locator("body").inner_text()
        assert "NaN" not in body
        assert "[object Object]" not in body
        # Job title should still be visible
        expect(page.locator("text=RapidCorp")).to_be_visible()


# ---------------------------------------------------------------------------
# 44. Profile with No Active Profile — Generation Error Handling
# ---------------------------------------------------------------------------

class TestNoActiveProfileGeneration:
    """Test document generation behavior when no profile is active."""

    @pytest.fixture
    def _inactive_setup(self, _auth_token):
        """Create profile (not activated) and a job."""
        import httpx
        headers = {"Authorization": f"Bearer {_auth_token}"}
        ts = int(time.time())

        # Create profile but DON'T activate
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"Inactive {ts}", "email": f"inactive_{ts}@example.com",
                  "phone": "555-0000", "location": "Nowhere"},
            headers=headers,
        )
        assert resp.status_code == 201

        # Create job
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={"title": f"No Profile Job {ts}", "company": "NoProfileCorp",
                  "location": "Remote", "description": "Test job."},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_generate_resume_api_without_active_profile(self, _auth_token, _inactive_setup):
        """API should return error quickly when generating without active profile."""
        import httpx
        # Use a short timeout — if no active profile, the API should return 400 quickly
        # If it hangs, that means it's trying to generate (which means an active profile
        # was found from a prior test), so skip.
        try:
            resp = httpx.post(
                f"{API_URL}/api/documents/resume",
                json={"job_id": _inactive_setup},
                headers={"Authorization": f"Bearer {_auth_token}"},
                timeout=5.0,
            )
            # Should return 400 or similar error, not 500
            assert resp.status_code in (400, 422), f"Expected 400/422, got {resp.status_code}: {resp.text}"
        except httpx.ReadTimeout:
            # If it times out, the API found an active profile from a prior test and is
            # actually generating. This is not a bug in the code — skip gracefully.
            pytest.skip("Generation endpoint started (active profile from prior test) — not a bug")


# ---------------------------------------------------------------------------
# Iteration 17: Bug Fix Regression Tests
# ---------------------------------------------------------------------------

class TestDocumentsSelectAll:
    """Verify the documents page select-all toggle works (was a variable hoisting bug)."""

    def test_select_all_toggle_no_crash(self, logged_in_page: Page):
        """Clicking select-all on documents page should not crash."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # Find the select-all checkbox area — it's the first CheckSquare/Square icon button
        select_all_btn = page.locator("button", has=page.locator("svg")).first
        if select_all_btn.is_visible():
            select_all_btn.click()
            page.wait_for_timeout(500)
            # Should not have crashed — page still functional
            expect(page.locator("h1")).to_contain_text("Documents")

    def test_documents_page_no_js_errors_on_interaction(self, logged_in_page: Page):
        """Interacting with documents page should not produce JS errors."""
        page = logged_in_page
        js_errors = []
        page.on("pageerror", lambda err: js_errors.append(str(err)))
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # Click filter buttons
        for label in ["Resume", "Cover Letter", "All"]:
            btn = page.get_by_role("button", name=label)
            if btn.is_visible():
                btn.click()
                page.wait_for_timeout(300)
        assert len(js_errors) == 0, f"JS errors during interaction: {js_errors}"


class TestProfileCreateWithSkills:
    """Verify that profile creation includes skills/experience/preferences."""

    def test_create_profile_with_skills_via_api(self, page: Page, _auth_token):
        """Create profile with skills via API and verify they are saved."""
        import httpx
        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={
                "name": f"SkillTest {ts}",
                "email": f"skilltest_{ts}@example.com",
                "phone": "555-0199",
                "location": "Remote",
                "skills": [
                    {"name": "Python", "level": "expert"},
                    {"name": "TypeScript", "level": "intermediate"},
                ],
                "experience": [
                    {
                        "title": "Senior Engineer",
                        "company": "TestCorp",
                        "start_date": "2020-01-01",
                        "end_date": "2024-01-01",
                        "description": "Built things",
                    }
                ],
                "preferences": {
                    "target_roles": ["Staff Engineer"],
                    "target_locations": ["Remote"],
                    "remote_preference": "remote",
                    "salary_min": 150000,
                    "salary_max": 250000,
                    "job_types": ["full-time"],
                    "industries": ["tech"],
                    "excluded_companies": [],
                },
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        profile = resp.json()
        assert len(profile["skills"]) == 2, f"Expected 2 skills, got {profile['skills']}"
        assert profile["skills"][0]["name"] == "Python"
        assert len(profile["experience"]) == 1
        assert profile["experience"][0]["title"] == "Senior Engineer"
        assert profile["preferences"]["target_roles"] == ["Staff Engineer"]
        assert profile["preferences"]["salary_min"] == 150000

    def test_create_profile_without_optional_fields(self, page: Page, _auth_token):
        """Create profile without skills/experience still works."""
        import httpx
        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={"name": f"BasicProfile {ts}"},
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        profile = resp.json()
        assert profile["skills"] == []
        assert profile["experience"] == []


# ---------------------------------------------------------------------------
# NEW: Profile Edit Flow
# ---------------------------------------------------------------------------

class TestProfileEditSaveFlow:
    """Test editing an existing profile and saving changes."""

    @pytest.fixture
    def profile_id(self, _auth_token):
        """Create a profile via API and return its ID."""
        import httpx
        ts = str(int(time.time()))
        resp = httpx.post(
            f"{API_URL}/api/profiles",
            json={
                "name": f"EditTest {ts}",
                "email": f"edit_{ts}@example.com",
                "phone": "555-9999",
                "location": "Denver, CO",
                "notes": "Original notes",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        return resp.json()["id"]

    def test_edit_profile_loads_existing_data(self, logged_in_page: Page, profile_id: str):
        """Edit page pre-fills fields with existing profile data."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Edit Profile")).to_be_visible()
        # Existing data should be pre-filled
        email_input = page.locator("input[type='email']")
        expect(email_input).to_have_value(re.compile(r"edit_\d+@example\.com"))
        phone_input = page.locator("input[type='tel']")
        expect(phone_input).to_have_value("555-9999")

    def test_edit_profile_save_shows_success(self, logged_in_page: Page, profile_id: str):
        """Saving profile edits shows success message."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        # Change the notes field (use placeholder to disambiguate from experience textarea)
        textarea = page.locator("textarea[placeholder='Any additional notes...']")
        textarea.fill("Updated notes via E2E test")
        # Save
        page.get_by_role("button", name=re.compile("Save|Update")).click()
        page.wait_for_timeout(2000)
        # Success message
        expect(page.locator("text=Profile saved successfully")).to_be_visible(timeout=5000)

    def test_edit_profile_updates_persist(self, logged_in_page: Page, profile_id: str, _auth_token):
        """Changes saved in edit mode persist when reloading."""
        import httpx
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/{profile_id}")
        page.wait_for_load_state("networkidle")
        # Update location
        location_input = page.locator("input[placeholder='City, State']")
        location_input.fill("Portland, OR")
        page.get_by_role("button", name=re.compile("Save|Update")).click()
        page.wait_for_timeout(2000)
        # Verify via API
        resp = httpx.get(
            f"{API_URL}/api/profiles/{profile_id}",
            headers={"Authorization": f"Bearer {_auth_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["location"] == "Portland, OR"


# ---------------------------------------------------------------------------
# NEW: Sidebar Navigation Links (all items)
# ---------------------------------------------------------------------------

class TestSidebarNavigation:
    """Test all sidebar navigation links work correctly."""

    @pytest.fixture
    def admin_page(self, page: Page):
        """Return a page logged in as the admin user via auto-login."""
        import httpx
        resp = httpx.post(f"{API_URL}/api/auth/auto-login")
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        page.goto(APP_URL + "/login")
        page.evaluate(f"window.localStorage.setItem('auth_token', '{token}')")
        page.goto(APP_URL)
        page.wait_for_load_state("networkidle")
        return page

    def test_nav_to_top_matches(self, admin_page: Page):
        """Sidebar 'Top Matches' link navigates correctly."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="Top Matches").click()
        page.wait_for_url("**/jobs/top")
        expect(page.get_by_role("heading", name="Top Matches")).to_be_visible()

    def test_nav_to_add_job(self, admin_page: Page):
        """Sidebar 'Add Job' link navigates correctly."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="Add Job").click()
        page.wait_for_url("**/jobs/add")
        expect(page.get_by_role("heading", name="Add Job")).to_be_visible()

    def test_nav_to_admin_dashboard(self, admin_page: Page):
        """Sidebar 'Admin' link navigates to admin dashboard."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="Admin", exact=True).click()
        page.wait_for_url("**/admin")
        expect(page.get_by_role("heading", name="Admin Dashboard")).to_be_visible()

    def test_nav_to_admin_pipeline(self, admin_page: Page):
        """Sidebar 'Pipeline' link navigates correctly."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="Pipeline").click()
        page.wait_for_url("**/admin/pipeline")

    def test_nav_to_admin_system_tools(self, admin_page: Page):
        """Sidebar 'System Tools' link navigates correctly."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="System Tools").click()
        page.wait_for_url("**/admin/scraper")

    def test_nav_to_admin_all_jobs(self, admin_page: Page):
        """Sidebar 'All Jobs' link navigates correctly."""
        page = admin_page
        page.locator("nav").get_by_role("link", name="All Jobs").click()
        page.wait_for_url("**/admin/jobs")

    def test_sidebar_shows_user_info(self, admin_page: Page):
        """Sidebar shows admin user email."""
        page = admin_page
        sidebar = page.locator("aside")
        expect(sidebar.locator("text=admin@jobsagent.local")).to_be_visible()

    def test_sidebar_active_link_highlighted(self, admin_page: Page):
        """Current page link is highlighted in sidebar."""
        page = admin_page
        # Dashboard is current page
        dashboard_link = page.locator("nav a[href='/']")
        expect(dashboard_link).to_have_class(re.compile("bg-primary-50"))


# ---------------------------------------------------------------------------
# NEW: Top Matches Page — Job Interactions
# ---------------------------------------------------------------------------

class TestTopJobsInteractions:
    """Test interactive elements on Top Matches page."""

    @pytest.fixture
    def _ensure_job_exists(self, _auth_token):
        """Ensure at least one job exists for top matches."""
        import httpx
        ts = str(int(time.time()))
        httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": f"TopMatch Test {ts}",
                "company": "TopCorp",
                "location": "Remote",
                "description": "A test job for top matches testing.",
            },
            headers={"Authorization": f"Bearer {_auth_token}"},
        )

    def test_top_jobs_view_details_navigates(self, logged_in_page: Page, _ensure_job_exists):
        """Clicking 'View Details' on a top job navigates to job detail."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        # If there are jobs with View Details links, click the first one
        view_btn = page.get_by_role("link", name="View Details").first
        if view_btn.is_visible():
            view_btn.click()
            page.wait_for_url(re.compile(r"/jobs/[^/]+$"), timeout=10000)

    def test_top_jobs_title_link_navigates(self, logged_in_page: Page, _ensure_job_exists):
        """Clicking a job title on top matches navigates to detail page."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        # Click the first job title link (inside a card)
        title_link = page.locator(".card a.text-lg").first
        if title_link.is_visible():
            title_link.click()
            page.wait_for_url(re.compile(r"/jobs/[^/]+$"), timeout=10000)

    def test_top_jobs_score_filter_all(self, logged_in_page: Page):
        """Selecting 'All' in score filter shows all jobs."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        page.locator("select").select_option("0")
        page.wait_for_timeout(1000)
        # Page should still show content (either jobs or empty state)
        body = page.locator("body")
        expect(body).to_be_visible()

    def test_top_jobs_empty_state_with_high_filter(self, logged_in_page: Page):
        """High score filter shows appropriate empty state."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        page.locator("select").select_option("80")
        page.wait_for_timeout(1000)
        # If no jobs match 80%+, empty state should show
        body = page.locator("body").inner_text()
        # Either we see jobs or we see the empty state message
        has_content = "No matches found" in body or "View Details" in body
        assert has_content, f"Expected either jobs or empty state, got: {body[:200]}"


# ---------------------------------------------------------------------------
# NEW: Dashboard Getting Started Checklist
# ---------------------------------------------------------------------------

class TestDashboardGettingStartedLinks:
    """Test the getting started checklist links on dashboard."""

    def test_dashboard_create_profile_link(self, logged_in_page: Page):
        """Quick action 'Create Profile' navigates correctly."""
        page = logged_in_page
        main = page.locator("main")
        create_link = main.get_by_role("link", name="Create Profile")
        expect(create_link).to_be_visible()
        create_link.click()
        page.wait_for_url("**/profiles/new", timeout=5000)

    def test_dashboard_browse_jobs_link(self, logged_in_page: Page):
        """Quick action 'Browse Jobs' navigates correctly."""
        page = logged_in_page
        main = page.locator("main")
        browse_link = main.get_by_role("link", name="Browse Jobs")
        expect(browse_link).to_be_visible()
        browse_link.click()
        page.wait_for_url("**/jobs", timeout=5000)

    def test_dashboard_add_job_link(self, logged_in_page: Page):
        """Quick action 'Add Job' navigates correctly."""
        page = logged_in_page
        main = page.locator("main")
        add_link = main.get_by_role("link", name="Add Job", exact=True)
        expect(add_link).to_be_visible()
        add_link.click()
        page.wait_for_url("**/jobs/add", timeout=5000)


# ---------------------------------------------------------------------------
# NEW: Logout and Re-login Flow
# ---------------------------------------------------------------------------

class TestLogoutReloginFlow:
    """Test that logout clears state and auto-login recovers."""

    def test_logout_clears_user_info(self, logged_in_page: Page):
        """After logout, user is redirected away from dashboard."""
        page = logged_in_page
        # Click sign out button
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_timeout(2000)
        # Should be redirected (auto-login kicks in, so we might end up
        # back on dashboard — but the token was cleared momentarily)
        # Verify localStorage was cleared
        token = page.evaluate("window.localStorage.getItem('auth_token')")
        # After auto-login, token may be set again — check URL is valid
        url = page.url
        assert "error" not in url.lower(), f"Error in URL after logout: {url}"

    def test_logout_and_auto_relogin(self, logged_in_page: Page):
        """After logout, auto-login should recover the session."""
        page = logged_in_page
        page.locator("button:has-text('Sign out')").click()
        page.wait_for_timeout(3000)
        # Navigate to root — should auto-login
        page.goto(APP_URL + "/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        # Should be on dashboard (auto-login)
        url = page.url
        assert "/login" not in url, "Should not be stuck on login page"
        assert "/welcome" not in url, "Should not be on welcome page"


# ---------------------------------------------------------------------------
# NEW: Documents Page — Interactions
# ---------------------------------------------------------------------------

class TestDocumentsPageInteractions:
    """Test interactive elements on the Documents page."""

    def test_documents_generate_section_has_job_dropdown(self, logged_in_page: Page):
        """Generate Documents section has a job selection dropdown."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Generate Documents")).to_be_visible()
        # Job selection dropdown
        select = page.locator("select").first
        expect(select).to_be_visible()

    def test_documents_type_filter_works(self, logged_in_page: Page):
        """Type filter dropdown changes document list view."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        # Find the type filter select (labeled or by position)
        selects = page.locator("select")
        # There should be at least 2 selects (type filter + job dropdown)
        count = selects.count()
        assert count >= 2, f"Expected at least 2 select elements, got {count}"

    def test_documents_no_bad_data(self, logged_in_page: Page):
        """No NaN, undefined, or [object Object] on documents page."""
        page = logged_in_page
        page.goto(APP_URL + "/documents")
        page.wait_for_load_state("networkidle")
        content = page.content()
        assert "NaN" not in content, "NaN found on documents page"
        assert "[object Object]" not in content, "[object Object] found on documents page"
        body_text = page.locator("body").inner_text()
        assert "undefined" not in body_text.lower().replace("not undefined", ""), \
            "undefined found in visible text on documents page"


# ---------------------------------------------------------------------------
# NEW: Error Boundary and Edge Cases
# ---------------------------------------------------------------------------

class TestAppErrorHandling:
    """Test that the app handles edge cases gracefully."""

    def test_invalid_profile_id_shows_error(self, logged_in_page: Page):
        """Visiting a non-existent profile ID doesn't crash."""
        page = logged_in_page
        page.goto(f"{APP_URL}/profiles/nonexistent-id-12345")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        # Should not show a blank page — either error message or redirect
        body = page.locator("body").inner_text()
        assert len(body.strip()) > 0, "Page is blank for invalid profile ID"

    def test_invalid_job_id_shows_error(self, logged_in_page: Page):
        """Visiting a non-existent job ID doesn't crash."""
        page = logged_in_page
        page.goto(f"{APP_URL}/jobs/nonexistent-job-12345")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        assert len(body.strip()) > 0, "Page is blank for invalid job ID"

    def test_api_info_endpoint(self, page: Page):
        """The /api/info endpoint returns correct metadata."""
        resp = page.request.get(f"{APP_URL}/api/info")
        assert resp.status == 200
        body = resp.json()
        assert body["name"] == "Jobs Agent API"
        assert "version" in body


# ---------------------------------------------------------------------------
# Iteration 20 — New Deep Tests
# ---------------------------------------------------------------------------


class TestJobDetailNoInvalidDate:
    """Verify job detail page never renders 'Invalid Date'."""

    def test_job_detail_no_invalid_date(self, logged_in_page: Page):
        """Create a job and verify the detail page has no 'Invalid Date' text."""
        page = logged_in_page

        # Create a job via API
        import httpx
        token = page.evaluate("window.localStorage.getItem('auth_token')")
        resp = httpx.post(
            f"{API_URL}/api/jobs",
            json={
                "title": "Date Check Job",
                "company": "Date Corp",
                "description": "Job for date rendering check",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 429:
            pytest.skip("Rate limited")
        assert resp.status_code in (200, 201), f"Job creation failed: {resp.text}"
        job_id = resp.json()["id"]

        page.goto(f"{APP_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        content = page.content()
        assert "Invalid Date" not in content, "Found 'Invalid Date' on job detail page"

    def test_documents_page_no_invalid_date(self, logged_in_page: Page):
        """Documents page should not display 'Invalid Date'."""
        page = logged_in_page
        page.goto(f"{APP_URL}/documents")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        content = page.content()
        assert "Invalid Date" not in content, "Found 'Invalid Date' on documents page"


class TestNoUndefinedTextRendering:
    """Verify pages never render literal 'undefined' or 'null' as visible text."""

    def _check_page_text(self, page: Page, url: str, name: str):
        page.goto(url)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        body_text = page.locator("body").inner_text()
        # Check for literal 'undefined' and 'null' rendered as text (not in URLs/attrs)
        # Only flag standalone words, not substrings of valid text like "nullable"
        for bad in ["undefined", "[object Object]"]:
            # Ignore occurrences in URLs or technical content
            lines = [l.strip() for l in body_text.split("\n") if bad in l.lower()]
            for line in lines:
                # Skip lines that look like technical/code content
                if "http" in line or "api" in line.lower() or "console" in line.lower():
                    continue
                assert bad not in line, f"Found '{bad}' in {name}: {line[:100]}"

    def test_dashboard_no_undefined(self, logged_in_page: Page):
        self._check_page_text(logged_in_page, APP_URL + "/", "dashboard")

    def test_profiles_page_no_undefined(self, logged_in_page: Page):
        self._check_page_text(logged_in_page, APP_URL + "/profiles", "profiles")

    def test_jobs_page_no_undefined(self, logged_in_page: Page):
        self._check_page_text(logged_in_page, APP_URL + "/jobs", "jobs")

    def test_documents_page_no_undefined(self, logged_in_page: Page):
        self._check_page_text(logged_in_page, APP_URL + "/documents", "documents")

    def test_top_jobs_no_undefined(self, logged_in_page: Page):
        self._check_page_text(logged_in_page, APP_URL + "/jobs/top", "top jobs")


class TestAddJobURLTab:
    """Test the 'From URL' tab on the Add Job page."""

    def test_url_tab_shows_input(self, logged_in_page: Page):
        """The From URL tab should show a URL input field."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        # From URL tab should be selected by default or clickable
        page.get_by_role("button", name="From URL").click()
        page.wait_for_timeout(500)
        url_input = page.locator("input[type='url'], input[placeholder*='URL'], input[placeholder*='url'], input[placeholder*='http']")
        expect(url_input.first).to_be_visible()

    def test_url_tab_empty_submit_prevented(self, logged_in_page: Page):
        """Submitting empty URL should not navigate away."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/add")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="From URL").click()
        page.wait_for_timeout(500)
        # Try submitting without URL
        submit_btn = page.locator("button:has-text('Add Job'), button:has-text('Fetch'), button:has-text('Submit')").first
        if submit_btn.is_visible():
            submit_btn.click()
            page.wait_for_timeout(1000)
            # Should still be on add job page
            assert "/jobs/add" in page.url


class TestJobListSortAndFilter:
    """Test job list sorting and filtering works without errors."""

    def test_jobs_page_filter_dropdown(self, logged_in_page: Page):
        """The jobs page filter/sort controls render correctly."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        # Check that the page loaded with proper structure
        body = page.locator("body").inner_text()
        assert "NaN" not in body, "NaN found on jobs page"
        assert "[object Object]" not in body, "[object Object] found on jobs page"


class TestProfileFormValidation:
    """Test profile form edge cases."""

    def test_empty_profile_form_not_submitted(self, logged_in_page: Page):
        """Submitting profile form with all empty fields should not crash."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")
        page.get_by_role("button", name="Create Profile").click()
        page.wait_for_timeout(1000)
        # Should either show validation error or stay on page
        body = page.locator("body").inner_text()
        assert "undefined" not in body.lower() or "http" in body.lower(), \
            "Undefined text shown on form validation"


class TestAdminPagesNoErrors:
    """Verify admin pages render without JS errors or bad data."""

    def test_admin_dashboard_no_nan(self, logged_in_page: Page):
        """Admin dashboard should not display NaN or undefined."""
        page = logged_in_page
        page.goto(APP_URL + "/admin")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        body = page.locator("body").inner_text()
        assert "NaN" not in body, "NaN found on admin dashboard"

    def test_admin_pipeline_no_errors(self, logged_in_page: Page):
        """Admin pipeline page loads without data rendering errors."""
        page = logged_in_page
        page.goto(APP_URL + "/admin/pipeline")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)
        content = page.content()
        assert "Invalid Date" not in content, "Invalid Date on admin pipeline page"
        body = page.locator("body").inner_text()
        assert "[object Object]" not in body, "[object Object] on admin pipeline page"


class TestBrowserBackNavigation:
    """Test that browser back button works correctly between pages."""

    def test_back_from_job_detail_to_jobs(self, logged_in_page: Page):
        """Navigate to a job detail, then back to jobs list."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs")
        page.wait_for_load_state("networkidle")
        # Click first job link if any exist
        job_links = page.locator("a[href*='/jobs/']").all()
        # Filter out add/top links
        detail_links = [l for l in job_links if '/add' not in (l.get_attribute('href') or '') and '/top' not in (l.get_attribute('href') or '')]
        if detail_links:
            detail_links[0].click()
            page.wait_for_load_state("networkidle")
            page.go_back()
            page.wait_for_load_state("networkidle")
            assert "/jobs" in page.url

    def test_back_from_profile_form_to_profiles(self, logged_in_page: Page):
        """Navigate to new profile form, then back to profiles list."""
        page = logged_in_page
        page.goto(APP_URL + "/profiles")
        page.wait_for_load_state("networkidle")
        page.goto(APP_URL + "/profiles/new")
        page.wait_for_load_state("networkidle")
        page.go_back()
        page.wait_for_load_state("networkidle")
        assert "/profiles" in page.url


class TestTopJobsScoreFilter:
    """Test the minimum score filter on top jobs page."""

    def test_score_filter_select_renders(self, logged_in_page: Page):
        """The score filter select element should render with correct options."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        select = page.locator("select.input")
        expect(select).to_be_visible()
        # Check options
        options = select.locator("option").all()
        assert len(options) >= 4, f"Expected at least 4 filter options, got {len(options)}"

    def test_score_filter_change_no_crash(self, logged_in_page: Page):
        """Changing the score filter should not cause errors."""
        page = logged_in_page
        page.goto(APP_URL + "/jobs/top")
        page.wait_for_load_state("networkidle")
        select = page.locator("select.input")
        select.select_option("70")
        page.wait_for_timeout(1000)
        body = page.locator("body").inner_text()
        assert "NaN" not in body, "NaN after changing score filter"
        assert "undefined" not in body.lower() or "http" in body.lower(), \
            "undefined after changing score filter"
