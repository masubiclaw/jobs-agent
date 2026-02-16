# Test Plan

**Date**: 2026-02-14
**Status**: Partially executed (see results column)

---

## 1. API Tests

| ID | Test | Method | Expected | Result |
|----|------|--------|----------|--------|
| API-01 | Health check | GET /api/health | 200, status: healthy | PASS |
| API-02 | Register new user | POST /api/auth/register | 201, user created | PASS |
| API-03 | Register duplicate email | POST /api/auth/register | 400, already exists | PASS |
| API-04 | Login valid credentials | POST /api/auth/login | 200, access_token | PASS |
| API-05 | Login invalid password | POST /api/auth/login | 401, invalid | PASS |
| API-06 | Login nonexistent user | POST /api/auth/login | 401, not found | PASS |
| API-07 | Get current user | GET /api/auth/me | 200, user data | PASS |
| API-08 | Access protected route without token | GET /api/profiles | 403, unauthorized | PASS |
| API-09 | Access with expired token | GET /api/profiles | 401 | NOT RUN |
| API-10 | Create profile | POST /api/profiles | 200, profile created | PASS |
| API-11 | List user profiles | GET /api/profiles | 200, array | PASS |
| API-12 | Update profile | PUT /api/profiles/:id | 200, updated | PASS |
| API-13 | Delete profile | DELETE /api/profiles/:id | 200 | PASS |
| API-14 | Access other user's profile | GET /api/profiles/:other_id | 404 | PASS |
| API-15 | Add job manually | POST /api/jobs | 200, job created | PASS |
| API-16 | List jobs with pagination | GET /api/jobs?page=1&page_size=20 | 200, paginated | PASS |
| API-17 | Search jobs | GET /api/jobs?query=engineer | 200, filtered | PASS |
| API-18 | Get job by ID | GET /api/jobs/:id | 200, job details | PASS |
| API-19 | Update job status | PUT /api/jobs/:id | 200, updated | PASS |
| API-20 | Delete job | DELETE /api/jobs/:id | 200, deleted | PASS |
| API-21 | Get top matches | GET /api/jobs/top | 200, sorted by score | PASS |
| API-22 | Generate resume | POST /api/documents/resume | 200, document | NOT RUN (requires Ollama) |
| API-23 | Generate cover letter | POST /api/documents/cover-letter | 200, document | NOT RUN (requires Ollama) |
| API-24 | List documents | GET /api/documents | 200, array | PASS |
| API-25 | Download document PDF | GET /api/documents/:id/download | 200, file | NOT RUN |
| API-26 | Admin stats (as admin) | GET /api/admin/stats | 200, stats | PASS |
| API-27 | Admin stats (as regular user) | GET /api/admin/stats | 403 | PASS |
| API-28 | Admin list users | GET /api/admin/users | 200, users | PASS |
| API-29 | Change password | POST /api/auth/change-password | 200 | PASS |

## 2. Frontend Tests

| ID | Test | Expected | Result |
|----|------|----------|--------|
| FE-01 | Login page renders | Form with email, password, submit | PASS (vitest) |
| FE-02 | Register page renders | Form with name, email, password, confirm | PASS (vitest) |
| FE-03 | Login form submission | Calls API, redirects to dashboard | PASS (vitest) |
| FE-04 | Register form validation | Shows error for mismatched passwords | PASS (vitest) |
| FE-05 | Jobs page renders | Page title, search, filter | PASS (vitest) |
| FE-06 | Jobs empty state | Shows "No jobs found" with CTA | PASS (vitest) |
| FE-07 | Documents page renders | Title, generate section, filters | PASS (vitest) |
| FE-08 | Profile form renders | All form fields present | PASS (vitest) |
| FE-09 | Layout navigation | All nav items rendered | PASS (vitest) |
| FE-10 | 404 page | Shows "Not Found" with back link | PASS (vitest) |
| FE-11 | API client auth header | Adds Bearer token to requests | PASS (vitest) |
| FE-12 | API client 401 handling | Clears token, redirects to login | PASS (vitest) |

**Frontend test results: 72/72 passed**

## 3. End-to-End Workflow

| ID | Test | Expected | Result |
|----|------|----------|--------|
| E2E-01 | Signup → Dashboard | New user sees dashboard | NOT RUN (manual) |
| E2E-02 | Create profile → Set active | Profile appears in sidebar stats | NOT RUN |
| E2E-03 | Add job → View details | Job appears in list and detail page | NOT RUN |
| E2E-04 | View top matches | Sorted by match score | NOT RUN |
| E2E-05 | Generate resume for job | PDF downloads | NOT RUN (requires Ollama) |
| E2E-06 | Status workflow | Change job status through pipeline | NOT RUN |

## 4. Edge Cases

| ID | Test | Expected | Result |
|----|------|----------|--------|
| EDGE-01 | Empty job description | Handled gracefully | PASS (shows "No description") |
| EDGE-02 | Very long job title | Truncated or wrapped | NOT VERIFIED |
| EDGE-03 | Missing match data | Score badge hidden | PASS (conditional render) |
| EDGE-04 | Rapid button clicks | No duplicate submissions | PASS (disabled state) |
| EDGE-05 | Browser back/forward | Correct page state | NOT VERIFIED |
| EDGE-06 | Token expiry mid-session | Redirect to login | PASS (401 interceptor) |

## 5. Security Tests

| ID | Test | Expected | Result |
|----|------|----------|--------|
| SEC-01 | XSS via dangerouslySetInnerHTML | Not used | PASS (grep confirms) |
| SEC-02 | JWT validation | Invalid tokens rejected | PASS |
| SEC-03 | CORS restricted origins | Only localhost allowed | PASS |
| SEC-04 | External links security | noopener noreferrer | PASS |
| SEC-05 | Admin endpoint protection | 403 for non-admins | PASS |
| SEC-06 | Rate limiting on login | Limits brute force | FAIL — No rate limiting |
| SEC-07 | Password hashing | Bcrypt used | PASS |
| SEC-08 | SQL injection | No SQL vectors | PASS (no SQL used) |

## Backend Test Results

**68 passed, 1 failed** (`test_scrape_single_source` — KeyError on `category` field)
- The failing test accesses a `category` key that's not returned by `scrape_single_source`
- This is a test bug, not a security issue

## Frontend Test Results

**72 passed, 0 failed**
