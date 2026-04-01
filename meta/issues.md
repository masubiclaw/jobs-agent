# Known Issues

## Fixed

### [MEDIUM] Generation error messages not styled red on Job Detail page
- **Date**: 2026-04-01
- **Severity**: MEDIUM
- **Component**: `web/src/pages/JobDetailPage.tsx`
- **Description**: The generation status message text color was determined by checking if the message string contained 'failed' or 'Failed'. Error messages that used different wording (e.g., "Document generation is temporarily unavailable. The AI service needs to be configured by the administrator.") displayed in gray (`text-gray-600`) instead of red (`text-red-600`), making them indistinguishable from informational messages.
- **Impact**: Users could miss that document generation had failed because the error message looked like a neutral status update.
- **Fix**: Added a separate `generationIsError` boolean state that is set to `true` in the `catch` block and `false` when generation starts. The message color now uses this boolean instead of parsing message text.

## Fixed in Iteration 1

### CRITICAL: API fails to start — google.adk import errors
- **Severity**: CRITICAL
- **Root cause**: `job_agent_coordinator/__init__.py` and `tools/__init__.py` eagerly imported `google.adk` modules which aren't installed in the web API venv. The `FunctionTool` import in 7 tool files and `Agent`/`LlmAgent` in sub_agents also failed.
- **Fix**: Made `google.adk` imports conditional with `try/except ImportError` fallbacks. Made `tools/__init__.py` use lazy `__getattr__` imports. Made `sub_agents/__init__.py` gracefully handle missing deps.

### HIGH: Port conflict — API port 8000 already in use
- **Severity**: HIGH
- **Root cause**: `start.sh` hardcoded port 8000 which was occupied by another service. Vite config used port 3000 but `start.sh` started it on 3001.
- **Fix**: Changed API to port 8002, vite default port to 3001, updated proxy target, added port 3001 to CORS allowed origins. Made ports configurable via variables in `start.sh`.

### MEDIUM: CORS missing port 3001
- **Severity**: MEDIUM
- **Root cause**: `start.sh` launched vite on port 3001 but CORS only allowed 3000 and 5173.
- **Fix**: Added `http://localhost:3001` and `http://127.0.0.1:3001` to CORS origins.

## Fixed (Iteration 14)

### [MEDIUM] ISSUE-001: No default admin user / login screen required
- **Date**: 2026-04-01
- **Severity**: MEDIUM (user feedback)
- **Component**: `api/routes/auth.py`, `api/main.py`, `web/src/contexts/AuthContext.tsx`, `web/src/api/auth.ts`
- **Description**: Users had to manually register and log in before using the app. No default admin existed.
- **Fix**: Added `/api/auth/auto-login` endpoint that creates a default admin user (`admin@jobsagent.local`) if needed and returns a JWT token. Frontend `AuthContext` calls this endpoint automatically when no token is stored, bypassing the login screen entirely. Default admin is also seeded on API startup if no users exist.

## Open Issues

None at this time.

## Fixed (Iteration 9)

### [HIGH] PDF download blocked by path traversal protection for generated_documents/
- **Date**: 2026-04-01
- **Severity**: HIGH
- **Component**: `api/services/document_service.py`
- **Description**: The `get_document_pdf()` method validates PDF paths against an allowlist of directories (`.job_cache`, `/tmp`). However, the PDF generator (`job_agent_coordinator/tools/pdf_generator.py`) saves generated PDFs to `generated_documents/`, which was not in the allowlist. This caused all PDF downloads to fail with a 404 and log a "Path traversal attempt blocked" warning.
- **Impact**: After successfully generating a resume or cover letter, users could not download the PDF. The download button silently failed because the API returned 404.
- **Fix**: Added `Path("generated_documents").resolve()` to the `allowed_dirs` list in `get_document_pdf()`.
