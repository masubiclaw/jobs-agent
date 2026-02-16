# Issues Log

**Last updated**: 2026-02-14

## User Feedback


---

## Security Issues


---

## Functional Issues



---

## UX Issues


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
