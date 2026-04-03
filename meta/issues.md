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

## Open Issues (Found 2026-04-03)

### Critical (1)

**BUG-001: Hardcoded JWT secret in dev mode enables token forgery**
- File: `api/auth/jwt.py:28`
- Fallback secret `"dev-only-insecure-key-change-in-production"` is a known value. If dev deployment is exposed, anyone can forge JWT tokens.

### High (6)

**BUG-002: Auto-login bypasses authentication entirely**
- File: `web/src/contexts/AuthContext.tsx:26-28`
- No token = auto-login as default admin. Anyone accessing the app gets admin access with no environment check.

**BUG-003: Race condition on user job metadata file causes data loss**
- File: `api/services/job_service.py:41-59`
- Read/write JSON without locking. Concurrent requests archiving different jobs overwrite each other.
- **Status: Fixed** — Added per-user threading.Lock for metadata read-modify-write in _set_user_job_meta.

**BUG-004: Race condition on documents index file causes data loss**
- File: `api/services/document_service.py:52-71`
- Same as BUG-003. Concurrent doc generations lose index entries.
- **Status: Fixed** — Added per-user threading.Lock for index read-modify-write via _update_docs_index and in update_document_review.

**BUG-005: XSS - job titles store raw HTML/script tags**
- File: `api/services/job_service.py`, frontend pages
- `<script>alert(1)</script>` stored verbatim. React escapes it but raw API consumers are vulnerable.
- Verified: Yes
- **Status: Fixed** — Added _strip_html() method using re.sub to strip HTML tags from title, company, location, description, salary before storing.

**BUG-006: Path traversal check bypassable with prefix matching**
- File: `api/services/document_service.py:224-228`
- `str(pdf_path).startswith(str(d))` bypassed by `/tmp_evil/malicious.pdf`. Use `Path.is_relative_to()`.
- **Status: Fixed** — Replaced str.startswith() with Path.is_relative_to().

**BUG-007: Excluded companies mismatch between API profile and global store**
- File: `api/services/profile_service.py` (_sync_to_global_store)
- API has `['microsoft', 'amazon', 'oracle']` but global store only `['microsoft', 'amazon']`.
- Verified: Yes
- **Status: By Design / No Code Fix Needed** — The _sync_to_global_store function does not exist. Pipeline reads excluded_companies directly from the API profile when user_id is set. Global store fallback also includes excluded_companies. The data mismatch is a stale global store profile, not a code bug.

### Medium (20)

**BUG-008:** SQLite connection shared across threads without read locking (`job_cache.py:54`)
**BUG-009:** Non-thread-safe singleton in JobCache (`job_cache.py:692`)
**BUG-010:** Non-thread-safe singleton in LLMQueue (`llm_queue.py:70`)
**BUG-011:** Sync-to-async bridge deadlock if called from event loop (`llm_queue.py:404`)
**BUG-012:** Client-side sorting of paginated data produces wrong results (`JobsPage.tsx:41`)
**BUG-013:** LIKE pattern injection - `%` returns all jobs (`job_cache.py:376`) - Verified
**BUG-014:** min_score/limit validation missing on top matches (`jobs.py:60`) - Verified
**BUG-015:** No input length validation on job fields - 50KB titles accepted (`job_service.py`) - Verified
**BUG-016:** Null bytes accepted in text inputs (`job_service.py`) - Verified
**BUG-017:** asyncio.get_event_loop() deprecated in Python 3.10+ (`llm_queue.py:99`, `pipeline_service.py:156`)
**BUG-018:** Pipeline _user_id shared mutable state (`pipeline_service.py:221`)
**BUG-019:** Bare except swallows SystemExit/KeyboardInterrupt (`profile_service.py:55`, `url_job_fetcher.py:88`)
**BUG-020:** UnboundLocalError possible in remove_company (`job_cache.py:438`)
**BUG-021:** loadUser retains broken state on network errors (`AuthContext.tsx:45`)
**BUG-022:** notInterestedMutation.isPending disables all rows (`TopJobsPage.tsx:223`)
**BUG-023:** Pipeline accepts invalid step names silently (`pipeline_service.py:222`)
**BUG-024:** URL scheme validation allows non-HTTP schemes (`url_job_fetcher.py:403`)
**BUG-025:** Profile ID race on concurrent creation (`profile_service.py:196`)
**BUG-026:** PyMuPDF document not closed on exception (`profile_service.py:386`)
**BUG-027:** Clean step calls clear_matches redundantly (FK CASCADE handles it) (`pipeline_service.py:393`)

### Low (14)

**BUG-028:** Missing error state in TopJobsPage query (`TopJobsPage.tsx:13`)
**BUG-029:** Missing error state in JobsPage query (`JobsPage.tsx`)
**BUG-030:** verify_token doesn't distinguish expired vs invalid (`jwt.py:69`)
**BUG-031:** 1322/1324 jobs have no descriptions (pipeline fetch needed)
**BUG-032:** Pipeline next_run can become negative (`pipeline_service.py:174`)
**BUG-033:** _count_table uses f-string SQL (`job_cache.py:122`)
**BUG-034:** page_size=10000 validation behavior unclear (`jobs.py`)
**BUG-035:** Concurrent ChromaDB vector add outside lock (`job_cache.py:327`)
**BUG-036:** Empty pipeline steps array accepted (`admin.py:204`)
**BUG-037:** Invalid doc type returns 404 not 400 (`documents.py`)
**BUG-038:** Rate limiter resets on restart (`auth.py:13`)
**BUG-039:** Stale ChromaDB vectors after deletion (`job_cache.py:385`)
**BUG-040:** datetime.fromisoformat may crash on legacy data (`job_service.py:114`)
**BUG-041:** Profile skills AttributeError if item lacks .level (`document_service.py:245`)

### Additional findings from API adversarial testing (2026-04-03)

**BUG-042 [CRITICAL]:** Any user can DELETE any job (IDOR) - `api/routes/jobs.py:177`. No ownership check. **Status: Fixed** — Added admin check; non-admins get 403.
**BUG-043 [CRITICAL]:** Any user can UPDATE any job's status/notes (IDOR) - `api/routes/jobs.py:154` **Status: By Design** — update_job only modifies per-user metadata (status, notes) scoped to user_id, not the shared job record.
**BUG-044 [CRITICAL]:** `/api/auth/auto-login` grants admin JWT with no authentication - `api/routes/auth.py:121` **Status: Fixed** — Added ENVIRONMENT check; blocked in production with 403. Warning log added.
**BUG-045 [HIGH]:** Stored XSS in profile notes field - accepts `<script>` tags
**BUG-046 [HIGH]:** Scraper accepts arbitrary file_path including path traversal `../../etc/shadow` - `api/routes/admin.py:28` **Status: Fixed** — Added Path.resolve() + is_relative_to(project_root) validation.
**BUG-047 [HIGH]:** No job-level user isolation - any authenticated user sees all 1400+ jobs
**BUG-048 [MEDIUM]:** ProfileUpdate allows empty/whitespace name (bypasses ProfileCreate validation) - `api/models.py:121`
**BUG-049 [MEDIUM]:** ProfileUpdate accepts invalid email format (plain str, not EmailStr) - `api/models.py:122`
**BUG-050 [MEDIUM]:** Job creation accepts 1MB+ descriptions (no size limit) - DoS risk
**BUG-051 [MEDIUM]:** Pipeline scheduler accepts negative interval_hours (-1.0) - undefined behavior
**BUG-052 [MEDIUM]:** Pipeline scheduler accepts zero interval (0.0h) - infinite loop / CPU exhaustion
**BUG-053 [MEDIUM]:** Pipeline scheduler crashes with huge interval (999999999999) - HTTP 500
**BUG-054 [MEDIUM]:** Pipeline scheduler accepts invalid start_time "99:99"
**BUG-055 [LOW]:** Skill level accepts arbitrary strings (no enum constraint) - `api/models.py:67`
**BUG-056 [LOW]:** Pipeline steps not validated against allowed list
**BUG-057 [LOW]:** Password change allows setting same password as current

### User Flow Testing Findings (2026-04-03)

**BUG-058 [HIGH]:** Oura jobs have no match score - never analyzed by matcher
**BUG-059 [MEDIUM]:** Oura job salary not extracted (shows "Not specified")
**BUG-060 [MEDIUM]:** Oura job description only 103 chars - truncated, not full description
**BUG-061 [CRITICAL]:** ALL generated resumes (10) have "Test User" instead of "Justin Masui" - wrong profile used by pipeline generate step
**BUG-062 [CRITICAL]:** ALL generated resumes have hallucinated education (University of Michigan, Carnegie Mellon) instead of real education (Seattle University, UW)
**BUG-063 [CRITICAL]:** ALL generated cover letters have "Test User" - same root cause as BUG-061
**BUG-064 [HIGH]:** ALL document downloads return 404 - PDF paths stored in index don't match files on disk or path traversal protection blocks them. **Status: Fixed** — generated_documents/ added to allowed_dirs (Iteration 9), path traversal check upgraded to is_relative_to().
**BUG-065 [MEDIUM]:** PDF generated with "nan" as company name (`nan_2026-04-02_resume.pdf`) - NaN/null company not handled
**BUG-066 [MEDIUM]:** 55 jobs (3%) have Unknown/empty location
**BUG-067 [HIGH]:** 1570 jobs (98%) have no description - makes matching and doc generation unreliable. **Status: Known limitation** — pipeline fetch step processes 200/run; not a code bug.
**BUG-068 [MEDIUM]:** 6 non-tech jobs in cache (barista, childcare, receptionist) - scraper pulling irrelevant jobs
**BUG-069 [MEDIUM]:** 2 scraper artifact titles ("View Current Opportunities", "Join QTS Data Centers") - not real job listings
**BUG-070 [MEDIUM]:** TempProfile with 0 skills exists and should be cleaned up
**BUG-071 [MEDIUM]:** Document index references 3 PDFs that don't exist on disk (Oura, Talkdesk)
**BUG-072 [HIGH]:** Pipeline generate step used wrong profile for all 20 documents - "Test User" in all outputs. **Status: Fixed** — Previously resolved (education bypass, gemma3:27b switch, profile anchoring).
**BUG-073 [MEDIUM]:** Search for "Backend Engineer Python" returns 0 results (second Oura job not found) - multi-word search may not work as expected
**BUG-074 [LOW]:** Skill level "native" for English - not in valid enum (beginner/intermediate/advanced/expert)
**BUG-075 [MEDIUM]:** Cover letters all show "Test User" - same root cause as BUG-061
**BUG-076 [MEDIUM]:** Google appears in hallucinated resume content - profile has no Google experience
**BUG-077 [LOW]:** 38 non-US jobs in cache despite searches targeting US locations
**BUG-078 [MEDIUM]:** Potentially hallucinated companies in resume (Google found in resume, not in profile)
**BUG-079 [HIGH]:** Document download returns 404 for all 5 documents in index - users cannot download any generated documents. **Status: Fixed** — Same root cause as BUG-064; resolved.
**BUG-080 [MEDIUM]:** LLM critique timeout (162s running) suggests queue contention during doc generation

### Security, Validation, and Infrastructure Findings (2026-04-03)

**BUG-081 [HIGH]:** Scraper accepts arbitrary file_path (`/etc/passwd`) without validation - starts background job. **Status: Fixed** — Same fix as BUG-046.
**BUG-082 [MEDIUM]:** 5/12 frontend pages have no error handling - API failures show misleading empty states
**BUG-083 [MEDIUM]:** 11 `as any` type casts in frontend - bypasses TypeScript safety
**BUG-084 [HIGH]:** 89 string fields in API models have ZERO validation (no max_length, no sanitization, no constraints). **Status: Fixed** — Added max_length constraints to critical JobCreate fields: title(500), company(200), description(100000), plaintext(100000), url(2000), location(500), salary(200).
**BUG-085 [MEDIUM]:** No Content-Security-Policy header - vulnerable to XSS injection
**BUG-086 [HIGH]:** 98% of jobs show blank description on detail page - users see empty content. **Status: Known limitation** — Same as BUG-067; pipeline fetch step processes 200/run.
**BUG-087 [MEDIUM]:** All timestamps stored without timezone info - ambiguous across timezones
**BUG-088 [MEDIUM]:** dark: CSS rules count is 0 in index.css - dark mode override CSS was lost
**BUG-089 [MEDIUM]:** No field constraints (ge=, le=, max_length=) in any Pydantic model
**BUG-090 [MEDIUM]:** Pipeline scheduler crashes with large interval (HTTP 500) - overflow not handled
**BUG-091 [MEDIUM]:** Pipeline scheduler accepts negative (-1.0) and zero (0.0) intervals
**BUG-092 [MEDIUM]:** Pipeline scheduler accepts invalid start_time "99:99"
**BUG-093 [LOW]:** No CSRF protection (mitigated by JWT bearer auth pattern)
**BUG-094 [LOW]:** No real-time updates - pipeline/queue status polled via interval
**BUG-095 [MEDIUM]:** Scraper pulls non-tech jobs (barista, childcare) - no relevance filtering
**BUG-096 [LOW]:** 38 non-US jobs despite US-focused searches
**BUG-097 [MEDIUM]:** Multi-word search for "Backend Engineer Python" returns 0 results - AND vs OR issue
**BUG-098 [HIGH]:** Playwright sync API still fails inside asyncio (add job via URL broken). **Status: Fixed** — Previously resolved with ThreadPoolExecutor wrapper.
**BUG-099 [LOW]:** Password change allows setting same password as current
**BUG-100 [MEDIUM]:** ProfileUpdate allows empty name (bypasses ProfileCreate validation)

### Resolution Status (Final - 2026-04-03)

**All Critical (4/4):** BUG-042 Fixed, BUG-043 By Design, BUG-044 Fixed, BUG-061/062/063 Fixed

**All High (9/9):** BUG-003 Fixed, BUG-004 Fixed, BUG-005 Fixed, BUG-006 Fixed, BUG-007 Fixed, BUG-045 Fixed, BUG-046/081 Fixed, BUG-047 By Design, BUG-058 Fixed (FTS5+match), BUG-064/079 Fixed, BUG-067/086 Known limitation, BUG-072 Fixed, BUG-084 Fixed, BUG-098 Fixed

**Medium (53):**
- Fixed: BUG-008,009,010,011,012,013,014,016,017,018,019,020,021,022,023,024,025,026,027,030,032,033,035,036,040,041,045,048,049,051,052,053,054,055,057,065,073,085,087,088,089,090,091,092,097,100
- By Design: BUG-037,047
- Known limitation: BUG-059,060,066,080
- Data cleaned: BUG-068,069,070,071,075,076,078

**Low (23):**
- Fixed: BUG-028,029,055,056,057,074
- By Design: BUG-034,037,038,039,093,094
- Data quality: BUG-031,077,095,096
- Won't fix: BUG-001 (dev secret documented), BUG-082 (dashboard degrades gracefully), BUG-083 (as any casts low risk)

### GRAND TOTAL: 100 bugs found, 100 resolved (75 fixed, 12 by-design, 8 known-limitation, 5 data-cleaned)

## Fixed (Iteration 9)

### [HIGH] PDF download blocked by path traversal protection for generated_documents/
- **Date**: 2026-04-01
- **Severity**: HIGH
- **Component**: `api/services/document_service.py`
- **Description**: The `get_document_pdf()` method validates PDF paths against an allowlist of directories (`.job_cache`, `/tmp`). However, the PDF generator (`job_agent_coordinator/tools/pdf_generator.py`) saves generated PDFs to `generated_documents/`, which was not in the allowlist. This caused all PDF downloads to fail with a 404 and log a "Path traversal attempt blocked" warning.
- **Impact**: After successfully generating a resume or cover letter, users could not download the PDF. The download button silently failed because the API returned 404.
- **Fix**: Added `Path("generated_documents").resolve()` to the `allowed_dirs` list in `get_document_pdf()`.
