# Issues Log

**Last updated**: 2026-02-16

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
