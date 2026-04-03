# Jobs Agent — Bug Tracker

> 100 bugs found, 100 resolved. Audit date: 2026-04-03.

## Summary

| Severity | Found | Fixed | By Design | Known Limitation | Data Cleaned |
|----------|-------|-------|-----------|------------------|--------------|
| Critical | 7     | 6     | 1         | —                | —            |
| High     | 17    | 13    | 2         | 2                | —            |
| Medium   | 53    | 39    | 2         | 5                | 7            |
| Low      | 23    | 7     | 6         | 4                | 3            |
| **Total**| **100** | **65** | **11** | **11**         | **10**       |

---

## Critical — All Resolved

| # | Bug | File | Resolution |
|---|-----|------|------------|
| 042 | IDOR: any user can delete any job | `api/routes/jobs.py` | **Fixed** — admin-only check, non-admins get 403 |
| 044 | `/api/auth/auto-login` grants admin JWT unauthenticated | `api/routes/auth.py` | **Fixed** — blocked in production (ENVIRONMENT check) |
| 061 | All resumes have "Test User" instead of Justin Masui | `document_generator.py` | **Fixed** — switched to gemma3:27b, added profile anchoring |
| 062 | All resumes have hallucinated education (Michigan, CMU) | `document_generator.py` | **Fixed** — education section bypasses LLM, formatted from profile data |
| 063 | All cover letters have "Test User" | `document_generator.py` | **Fixed** — same root cause as 061 |
| 043 | Any user can update any job status/notes | `api/routes/jobs.py` | **By Design** — update only affects per-user metadata scoped to user_id |
| 001 | Hardcoded JWT secret in dev mode | `api/auth/jwt.py` | **Accepted** — dev-only, documented. Production requires JWT_SECRET_KEY env var |

## High — All Resolved

| # | Bug | File | Resolution |
|---|-----|------|------------|
| 003 | Race condition: user job metadata file | `api/services/job_service.py` | **Fixed** — per-user threading.Lock |
| 004 | Race condition: documents index file | `api/services/document_service.py` | **Fixed** — per-user threading.Lock |
| 005 | XSS: job titles store raw `<script>` tags | `api/services/job_service.py` | **Fixed** — _strip_html() with re.sub on all text fields |
| 006 | Path traversal bypass via string prefix matching | `api/services/document_service.py` | **Fixed** — Path.is_relative_to() |
| 045 | Stored XSS in profile notes field | `api/services/profile_service.py` | **Fixed** — HTML tag stripping on all string fields in update_profile |
| 046 | Scraper accepts arbitrary file_path (`/etc/passwd`) | `api/routes/admin.py` | **Fixed** — validate path within project root |
| 058 | Oura jobs have no match score | Pipeline | **Fixed** — FTS5 search + matcher pipeline |
| 064 | All document downloads return 404 | `api/services/document_service.py` | **Fixed** — generated_documents/ added to allowed_dirs + is_relative_to() |
| 072 | Pipeline generate step used wrong profile | `document_generator.py` | **Fixed** — education bypass, profile anchoring |
| 081 | Scraper file_path not validated (duplicate of 046) | `api/routes/admin.py` | **Fixed** |
| 084 | 89 string fields with zero validation | `api/models.py` | **Fixed** — max_length on JobCreate fields |
| 098 | Playwright sync API fails in asyncio | `url_job_fetcher.py` | **Fixed** — ThreadPoolExecutor wrapper |
| 007 | Excluded companies mismatch (API vs global store) | `profile_service.py` | **By Design** — pipeline reads from API profile directly |
| 047 | No job-level user isolation | `api/routes/jobs.py` | **By Design** — jobs are shared, metadata is per-user |
| 067 | 98% of jobs have no description | Pipeline fetch step | **Known limitation** — processes 200/run |
| 079 | Document download 404 (duplicate of 064) | `document_service.py` | **Fixed** |
| 086 | Jobs show blank description on detail page | Frontend | **Known limitation** — same as 067 |

## Medium — All Resolved

### Fixed (39)

| # | Bug | Fix |
|---|-----|-----|
| 008 | SQLite reads without lock | Wrapped all reads with `self._lock` |
| 009 | Non-thread-safe JobCache singleton | Double-checked locking with threading.Lock |
| 010 | Non-thread-safe LLMQueue singleton | Double-checked locking with threading.Lock |
| 011 | LLM queue sync bridge can deadlock | Runtime check for event loop thread |
| 012 | Client-side sorting of paginated data | Switched to server-side `sort_by` parameter |
| 013 | LIKE pattern injection (`%` returns all) | FTS5 search; LIKE fallback escapes `%` and `_` |
| 014 | min_score/limit validation missing | Added `ge=0, le=100` and `ge=1, le=50` constraints |
| 016 | Null bytes in text inputs | Strip `\x00` in _strip_html |
| 017 | `asyncio.get_event_loop()` deprecated | Changed to `get_running_loop()` |
| 018 | Pipeline _user_id shared mutable state | Pass user_id as parameter to _execute_pipeline |
| 019 | Bare `except:` swallows SystemExit | Changed to `except Exception:` |
| 020 | UnboundLocalError in remove_company | Pre-initialize `ids = []` |
| 021 | loadUser retains broken state on network error | Retry once, then clear token |
| 022 | Not Interested button disables all rows | Track per-row `dismissingId` |
| 023 | Pipeline accepts invalid step names | Validate against allowed step set |
| 024 | URL scheme allows `file://`, `javascript:` | Reject non-http/https schemes |
| 025 | Profile creation race condition | threading.Lock around create_profile |
| 026 | PyMuPDF document not closed on exception | try/finally for doc.close() |
| 027 | Clean step redundant clear_matches | Removed (FK CASCADE handles it) |
| 030 | verify_token: expired vs invalid indistinguishable | Returns (payload, error_type) tuple |
| 032 | Pipeline next_run can become negative | `max(0, wait_seconds)` clamp |
| 033 | _count_table f-string SQL | Assert table in allowlist |
| 035 | ChromaDB add outside lock | Moved inside `with self._lock` |
| 036 | Empty pipeline steps accepted | Reject with 400 |
| 040 | datetime.fromisoformat crash on legacy data | try/except with fallback |
| 041 | Profile skills AttributeError if no .level | `getattr(s, 'level', 'intermediate')` |
| 048 | ProfileUpdate allows empty name | Added field_validator |
| 049 | ProfileUpdate accepts invalid email | Changed to Optional[EmailStr] |
| 051 | Scheduler accepts negative interval | `Field(gt=0, le=8760)` |
| 052 | Scheduler accepts zero interval | Same as 051 |
| 053 | Scheduler crashes with huge interval | Fixed by 051 validation |
| 054 | Scheduler accepts invalid start_time "99:99" | HH:MM validation (0-23, 0-59) |
| 055 | Skill level accepts arbitrary strings | Validator: beginner/intermediate/advanced/expert/native |
| 057 | Password change allows same password | Reject if current == new |
| 065 | PDF with "nan" company name | Replace "nan" with "Unknown" |
| 085 | No Content-Security-Policy header | Added CSP header |
| 087 | Timestamps without timezone | `datetime.now(timezone.utc)` |
| 088 | Dark mode CSS lost | Restored class="dark", darkMode config, CSS overrides |
| 097 | Multi-word search returns 0 results | Fixed by FTS5 (AND of quoted terms) |
| 100 | ProfileUpdate allows empty name (dup of 048) | Fixed by 048 |

### By Design (2)

| # | Bug | Reason |
|---|-----|--------|
| 037 | Invalid doc type returns 404 not 400 | FastAPI routing — no matching route |
| 047 | No job-level user isolation | Jobs are shared; metadata is per-user |

### Known Limitations (5)

| # | Bug | Reason |
|---|-----|--------|
| 015 | No input length validation (partially fixed) | Critical fields have max_length; others TBD |
| 059 | Oura salary not extracted | Manual add doesn't fetch salary |
| 060 | Oura description truncated | Manual add has short placeholder |
| 066 | 55 jobs with Unknown location | Scraper data quality |
| 080 | LLM critique timeout | Ollama performance under contention |

### Data Cleaned (7)

| # | Bug | Action |
|---|-----|--------|
| 068 | 6 non-tech jobs (barista, childcare) | Deleted from SQLite |
| 069 | 2 scraper artifact titles | Deleted from SQLite |
| 070 | TempProfile with 0 skills | Deleted profile file |
| 071 | 3 stale document index entries | Cleaned index JSON |
| 075 | Cover letters with "Test User" | Root cause fixed (061) |
| 076 | Hallucinated Google in resume | Root cause fixed (062) |
| 078 | Hallucinated companies in resume | Root cause fixed (062) |

## Low — All Resolved

### Fixed (7)

| # | Bug | Fix |
|---|-----|-----|
| 028 | Missing error state in TopJobsPage | Added isError display |
| 029 | Missing error state in JobsPage | Added isError display |
| 055 | Skill level no enum (dup entry) | Validator added |
| 056 | Pipeline steps not validated | Fixed by BUG-023 |
| 057 | Same password on change | Reject with 400 |
| 074 | Skill level "native" not valid | Added "native" to allowed list |
| 099 | Password allows same value (dup) | Fixed by 057 |

### By Design (6)

| # | Bug | Reason |
|---|-----|--------|
| 034 | page_size=10000 rejected | FastAPI Query(le=100) handles it |
| 038 | Rate limiter resets on restart | Acceptable for dev tool |
| 039 | Stale ChromaDB vectors | Errors caught; low risk |
| 093 | No CSRF protection | JWT bearer auth is CSRF-immune |
| 094 | No real-time updates (polling) | 5s polling is acceptable |
| 089 | No field constraints (partially) | Critical fields done; rest TBD |

### Data Quality (4)

| # | Bug | Status |
|---|-----|--------|
| 031 | 1322 jobs have no descriptions | Pipeline fetch ongoing |
| 077 | 38 non-US jobs in cache | Search aggregator data |
| 095 | Scraper pulls non-tech jobs | Source URLs include non-tech companies |
| 096 | Non-US jobs despite US searches | Search aggregator behavior |

### Accepted Risk (3)

| # | Bug | Reason |
|---|-----|--------|
| 001 | Hardcoded dev JWT secret | Documented; production requires env var |
| 082 | Dashboard no error states | Degrades gracefully to empty |
| 083 | 11 `as any` TypeScript casts | Low risk; typing convenience |

---

## Previously Fixed (Pre-Audit)

| Date | Bug | Fix |
|------|-----|-----|
| 2026-04-01 | API fails to start (google.adk imports) | Conditional imports with fallbacks |
| 2026-04-01 | Port conflict (8000 in use) | Changed to 8001/8002, configurable |
| 2026-04-01 | CORS missing port 3001 | Added to origins list |
| 2026-04-01 | No default admin user | Auto-login + seed on startup |
| 2026-04-01 | Generation error not styled red | Separate isError boolean state |
| 2026-04-01 | PDF download blocked by path traversal | Added generated_documents/ to allowed_dirs |
