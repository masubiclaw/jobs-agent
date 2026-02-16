# Issues Log

**Last updated**: 2026-02-16

## User Feedback


---

## Security Issues


---

## Functional Issues



---

## UX Issues

### UX-001 (FIXED)
- **Category**: CORRECTNESS
- **Severity**: CRITICAL
- **Observation**: Job Preferences (target roles, locations, remote preference, salary range, excluded companies) can be saved successfully — the PUT returns 200 — but navigating away and returning to the profile page shows the old/empty values. The preferences object is either not persisted to the profile store, not serialized correctly in TOON format, or the GET response is reconstructing from stale data. This is a data-loss bug: users fill out preferences, believe they're saved, and the matcher runs against an empty preference set.
- **Recommendation**: Trace the full round-trip: PUT /api/profiles/:id → ProfileService.update_profile → _save_profile → disk write → GET /api/profiles/:id → _load_profile → _to_response. Verify preferences are written to the .toon file and parsed back correctly. Add an integration test that saves preferences and reads them back.

### UX-002 (FIXED)
- **Category**: INTERACTION
- **Severity**: MAJOR
- **Observation**: Profile creation only supports PDF upload. Users who have their resume as plain text (copied from LinkedIn, a Google Doc, or typed up) have no way to paste it in. They'd need to create a PDF just to import it, which is unnecessary friction. The backend already has `_parse_resume_with_llm` which accepts raw text — the frontend just doesn't expose it.
- **Recommendation**: Add a "Paste Resume Text" tab/option alongside the PDF upload. POST the raw text to a new endpoint (e.g., POST /api/profiles/import/text) or reuse the LLM parsing path directly. A simple textarea with a "Parse" button is sufficient.

### UX-003 (FIXED)
- **Category**: INTERACTION
- **Severity**: MAJOR
- **Observation**: Experience entries are read-only after import. If the LLM mis-parses a job title, gets dates wrong, or truncates a description, the user cannot correct it inline. The only option is to delete the profile and re-import. This is especially painful given the 3+ minute PDF parse time.
- **Recommendation**: Make experience entries editable. Each entry (title, company, dates, description) should be inline-editable or open an edit modal. Wire up to the existing PUT /api/profiles/:id endpoint with the updated experience array.

### UX-004 (FIXED)
- **Category**: DATA_PRESENTATION
- **Severity**: MINOR
- **Observation**: Experience descriptions render as a single block of text. Resume bullet points (achievements, responsibilities) are collapsed into a wall of text, making it difficult to scan. This also means the LLM-generated output loses the structure that was present in the original resume.
- **Recommendation**: Parse description text for bullet-point patterns (lines starting with -, *, or •) and render as a `<ul>`. If the LLM prompt is producing run-on text, update the parsing prompt to explicitly request bullet-point format for descriptions.

### UX-005 (FIXED)
- **Category**: LEARNABILITY
- **Severity**: MAJOR
- **Observation**: When a PDF is uploaded, the UI shows a generic spinner with no indication of expected duration. The local LLM takes 3-5 minutes to parse a resume. Users assume it's frozen, navigate away, or close the tab — which may abort the request (the Cloudflare tunnel has its own timeout). There's no "don't leave" warning and no progress indicator.
- **Recommendation**: Show a message like "Parsing resume with local AI — this typically takes 3-5 minutes. Please don't navigate away." Add a `beforeunload` event listener while parsing is in progress. Consider adding a progress bar or elapsed-time counter. If possible, make the parse async (return 202, poll for completion) so navigation doesn't kill it.

### UX-006 (FIXED)
- **Category**: DATA_PRESENTATION
- **Severity**: MAJOR
- **Observation**: The All Jobs page displays "unknown" for fields like location, salary, or posted date when the scraper didn't capture them. This looks broken rather than intentional. 483 jobs with scattered "unknown" values erode trust in the data quality.
- **Recommendation**: Replace "unknown" with contextually appropriate fallbacks: em-dash (—) or hide the field entirely if empty. For location, show "Remote" only if confirmed; otherwise omit. For salary, omit rather than show "unknown". Filter or flag incomplete job records in the admin view.

### UX-007 (FIXED)
- **Category**: INTERACTION
- **Severity**: MAJOR
- **Observation**: System Tools (scraper, searcher, matcher, cleanup) fire off background tasks with no feedback. The UI shows no progress, no status, no elapsed time, and no way to cancel a running operation. The matcher can run for 10+ minutes processing 483 jobs through the local LLM. The user has no idea if it's working, stuck, or finished.
- **Recommendation**: Add real-time status for each tool: IDLE / RUNNING (with elapsed time) / COMPLETED (with summary) / FAILED (with error). Implement a cancel button that sends a signal to abort the background task. Use SSE or polling to update status. Show a summary when complete (e.g., "Matched 47 new jobs in 8m 23s").

### UX-008 (FIXED)
- **Category**: INTERACTION
- **Severity**: MINOR
- **Observation**: The scheduler only allows setting frequency intervals (e.g., "every 6 hours") but not specific times. Users who want the pipeline to run at 6 AM daily, or at a specific time to avoid competing with other Ollama workloads, cannot express that.
- **Recommendation**: Add a time picker for scheduled runs. Support cron-style scheduling: "daily at HH:MM" or "every N hours starting at HH:MM". Display the next scheduled run time.

### UX-009 (FIXED)
- **Category**: INFO_ARCHITECTURE
- **Severity**: MINOR
- **Observation**: The "Auto-Match" section name is ambiguous — it could mean automatic job matching, but it actually controls the full pipeline (scraping, searching, matching, cleanup). The name undersells the feature and confuses its scope. Admin users looking for pipeline controls might not find them under "Auto-Match".
- **Recommendation**: Rename to "Pipeline Admin" or "Pipeline Controls". The section should clearly communicate that it manages the end-to-end job discovery and matching pipeline, not just the matching step.

---

## Remaining Items

### ISSUE-003 (OPEN — mitigated)
- JWT in localStorage is a known trade-off. No XSS vectors exist in the codebase (grep confirms no dangerouslySetInnerHTML). Security headers provide additional protection. Full httpOnly cookie migration would require:
  - Server-side cookie setting on login
  - CSRF protection middleware
  - Frontend auth flow refactoring
  - This is a significant effort with low incremental security benefit given the current mitigations.

---

## User Feedback

- Profiles:  Job Preferences: saving these values are not reflected when coming back to profile page
- Profiles:  should also take copy and paste of plain text
- Profile:  should be able to edit the experience text
- Profile:  exprience text should be in bullet points
- Profile:  when uploading a pdf, give accurate estimate of how long it takes to parse.  Also message to not navigate away
- All Jobs:  should not have "unknown" 
- System Tools:  should show status of tool running and also have a way of cancelling.
- Scheduler should be able to pick a specific time
- Auto-Match:  should be named something better like 'pipeline admin'
