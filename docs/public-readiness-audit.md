# Public Readiness Audit

**Date**: 2026-02-14
**Auditor**: Claude Agent
**Goal**: Evaluate jobs-agent for public use by non-technical job seekers

---

## Executive Summary

**Overall Readiness: 6/10** — The app is functionally complete with solid auth, data isolation, and a polished UI for desktop. However, critical gaps in mobile support, onboarding, security hardening, and user guidance block public launch.

---

## 1. Onboarding

**Score: 4/10**

- **No landing page** — Unauthenticated users are redirected straight to `/login`. There's no explanation of what the app does, its value proposition, or how it works.
- **Login/Register pages** show only "Jobs Agent - Resume Builder" with no description.
- **No guided onboarding** — After registration, users land on a dashboard with no tutorial, walkthrough, or "getting started" guidance.
- **No profile setup prompt** — New users aren't directed to create a profile, which is required for matching and document generation.
- **Estimated time to first match**: 5-10 minutes (needs to be <3 minutes).

**Blockers**: A first-time visitor cannot understand what this app does without external context.

---

## 2. Core Workflow: Search → Match → Resume → Apply

**Score: 7/10**

- **Search**: Job search is functional via admin pipeline (scraper) and manual add. Users can search/filter existing jobs. However, regular users can't trigger job searches — only admins can run the scraper/searcher.
- **Match**: Two-pass matching works (keyword 20% + LLM 80%). Scores are displayed but **not explained** to users.
- **Resume**: Document generation works but requires Ollama running locally. Error message "Check Ollama is running" is confusing for non-technical users.
- **Apply**: No apply functionality. Users must manually visit the job URL. No application tracking beyond status updates.

**Blockers**: Regular users depend entirely on admins to populate job listings. The Ollama dependency makes self-hosting impractical for non-technical users.

---

## 3. Auth & Multi-tenancy

**Score: 7/10**

**Positive**:
- JWT authentication works correctly
- All data endpoints filter by user_id
- Profiles, jobs metadata, and documents are user-scoped
- Admin endpoints properly protected with role checks

**Issues**:
- Hardcoded admin email (`justin.masui@gmail.com`) — security backdoor
- JWT stored in localStorage (XSS vulnerability)
- No rate limiting on login/register
- JWT secret falls back to insecure dev key if env var unset
- 24-hour token expiration is too long

---

## 4. Error Handling

**Score: 7/10**

**Positive**:
- Global exception handler returns generic "Internal server error" (no stack traces)
- Frontend shows user-friendly error messages with fallbacks
- Login/register errors properly displayed

**Issues**:
- Network errors (API unreachable) show raw technical messages
- No global React error boundary — unhandled JS errors crash the app
- Long-running operations (PDF generation, LLM calls) lack timeout feedback
- Document generation failure says "Check Ollama is running" — meaningless to non-tech users

---

## 5. Performance

**Score: 7/10**

- Page loads are fast (Vite + React Query with 5min stale time)
- API responses are quick for CRUD operations
- Job search with pagination works well

**Issues**:
- No code splitting — entire app bundled together
- Client-side sorting on jobs page (not server-side)
- Document generation can take 30-60+ seconds with no progress indicator
- No skeleton screens (all pages use spinners)

---

## 6. Mobile

**Score: 3/10** — **CRITICAL GAP**

- **Sidebar is fixed-width (w-64)** with no hamburger menu. On mobile, it either overlaps content or makes the app unusable.
- **ProfileFormPage** uses `grid-cols-2` with no mobile breakpoint — forms display in 2 columns on phones.
- **JobDetailPage** status buttons don't wrap on small screens.
- **Pagination controls** don't have mobile-responsive classes.
- **DocumentsPage** action buttons overflow on mobile.

**Blocker**: Most job seekers browse on mobile. The app is currently desktop-only.

---

## 7. Security

**Score: 5/10**

### Critical
- **Hardcoded admin email** — backdoor for specific email address
- **JWT in localStorage** — vulnerable to XSS attacks
- **No rate limiting** — brute force attacks possible on auth endpoints
- **Weak JWT secret** — dev key used as fallback

### High
- **No path traversal protection** on PDF download
- **Admin scraper accepts arbitrary file paths**
- **No HTTPS enforcement**
- **No security headers** (CSP, X-Frame-Options, etc.)

### Positive
- No SQL injection vectors (no SQL used)
- Bcrypt password hashing
- No dangerouslySetInnerHTML in frontend
- External links properly secured (noopener noreferrer)
- Pydantic models validate all inputs
- File upload size limits enforced

---

## Summary: Must-Fix Before Public Launch

| Priority | Issue | Category |
|----------|-------|----------|
| P0 | Add mobile responsive layout with hamburger menu | Mobile |
| P0 | Remove hardcoded admin email | Security |
| P0 | Add rate limiting on auth endpoints | Security |
| P0 | Add landing page for unauthenticated users | Onboarding |
| P1 | Move JWT to httpOnly cookies | Security |
| P1 | Add global React error boundary | Error Handling |
| P1 | Explain match scores to users | UX |
| P1 | Fix responsive grids on ProfileFormPage | Mobile |
| P1 | Add security headers middleware | Security |
| P2 | Add onboarding flow after registration | Onboarding |
| P2 | Improve error messages for Ollama dependency | UX |
| P2 | Add code splitting | Performance |
| P2 | Add skeleton loading screens | Performance |
