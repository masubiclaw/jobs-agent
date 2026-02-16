# Mission: Build a Public-Ready Job Search Site

**IMPORTANT**: You are a leader agent running autonomously in a loop. Do NOT ask for confirmation, permission, or clarification. Execute every phase immediately without stopping. Never end your response with a question.

## Your Goal
Build jobs-agent into a site that **anyone** can use to find jobs. Think of it as a public-facing product — not a developer tool. Every decision should be made through the lens of: "Would a non-technical job seeker be able to use this without help?"

## Phase 0: Check Existing Issues & User Feedback
- Read `docs/ISSUES.md` first
- If there are OPEN issues (ISSUE-* or UX-*), fix and verify those before proceeding
- Check the **User Feedback** section — convert actionable feedback items into ISSUE-* or UX-*
  entries with highest severity, then fix them
- Mark each as FIXED in `docs/ISSUES.md` after verification
- Remove feedback items from the User Feedback section once converted to issues
- Only move to Phase 1 when all existing OPEN issues and user feedback are resolved

## Phase 1: Public Readiness Audit
Evaluate the current state against what's needed for public use:
- **Onboarding**: Can a new user sign up and find their first job match within 3 minutes?
- **Core workflow**: Search → Match → Resume → Apply. Is this flow obvious and complete?
- **Auth & multi-tenancy**: Is user data isolated? Can strangers' data leak?
- **Error handling**: Every failure state must show a human-friendly message, never a stack trace
- **Performance**: Pages load fast, searches return quickly, no spinners longer than 3s
- **Mobile**: Site must be usable on a phone — most job seekers browse on mobile
- **Security**: XSS, SQL injection, JWT validation, CORS, rate limiting, input sanitization

Write findings to `docs/public-readiness-audit.md`.

## Phase 2: Test Plan & Execute
Create a test plan in `docs/test-plan.md` covering:
- **API**: All endpoints, auth flows, error responses, edge cases
- **Frontend**: All pages, UI states (loading, empty, error, success), responsive behavior
- **Workflow**: End-to-end — signup, profile setup, job search, matching, resume generation
- **Edge cases**: Empty results, long text, missing data, rapid clicks, browser navigation
- **Auth**: Login, logout, session expiry, protected routes, multi-user isolation
- **Security**: XSS, injection, JWT, CORS, external links

Execute every test. For each failure, append to `docs/ISSUES.md`:
- **ID**: ISSUE-NNN (sequential)
- **Test ID**: reference from test plan
- **Severity**: CRITICAL | MAJOR | MINOR
- **Description**: what failed
- **Steps to reproduce**
- **Expected vs Actual**
- **Status**: OPEN

## Phase 3: User Experience Review

**Persona**: "Jamie" — mid-career professional, not technical. Has used LinkedIn and
Indeed but never a tool like this. Comfortable with basic web apps but confused by jargon,
scores without context, or unclear next steps. Evaluates it the way a real job seeker
would: "Does this help me find a job faster, or is it just confusing?"

**Evaluate through Jamie's eyes**:
- **First impression**: Does the landing page explain what this is and why Jamie should use it?
- **Learnability**: Can Jamie understand what to do within 2 minutes without reading docs?
- **Information architecture**: Is the hierarchy logical? Are related things grouped?
- **Data presentation**: Are job listings, match scores, and resume content clear and
  consistent? Are null/zero/empty states handled?
- **Interaction quality**: Do controls behave as expected? Is feedback immediate?
- **Terminology**: No jargon. "Match score" needs context. "NLP" means nothing to Jamie.
- **Trust & clarity**: Does Jamie trust the results? Are match scores explained? Does
  "85% match" mean anything without context?
- **Missing polish**: Dead links, placeholder text, inconsistent spacing, truncated content
- **Call to action**: At every step, is it clear what Jamie should do next?

Append findings to `docs/ISSUES.md` with:
- **ID**: UX-NNN (sequential, separate from ISSUE-NNN)
- **Category**: LEARNABILITY | INFO_ARCHITECTURE | DATA_PRESENTATION | INTERACTION | CONSISTENCY | POLISH | CORRECTNESS | ONBOARDING
- **Severity**: CRITICAL | MAJOR | MINOR
- **Observation**: what Jamie notices and why it's a problem
- **Recommendation**: specific fix
- **Status**: OPEN

## Phase 4: Fix & Verify Loop

### Pre-check
- Read `docs/ISSUES.md` first — check for any existing OPEN issues before creating new ones
- Do not duplicate issues already logged

### Prioritization
1. **User Feedback** — always highest priority, these are real user pain points
2. CRITICAL security/auth issues (blocks public launch)
3. CRITICAL UX issues (users can't complete core workflow)
4. MAJOR functional bugs
5. MAJOR UX issues
6. MINOR polish

### Constraints
- Do NOT skip regression testing after each fix
- Update docs/ISSUES.md after every fix, not in batch
- If a fix introduces a new issue, log it immediately and prioritize by severity
- UX-* issues are first-class — a CRITICAL polish problem blocks release just like a bug
- Max 10 iterations — if not converging, stop and report remaining issues
- Every change must work for a non-technical public user, not just developers
