# Jobs Agent — Technical Specification

> Living document. Auto-updated on session end via `.claude/settings.json` stop hook.

## 1. System Overview

Jobs Agent is an AI-powered job search platform that aggregates job listings, matches them against a user's profile, and generates tailored application documents (resume + cover letter). It runs as a local web application backed by Ollama for LLM inference.

**Architecture:** FastAPI backend + React frontend + SQLite storage + Ollama LLM

**Primary user flow:** Import resume PDF → system extracts profile → pipeline scrapes jobs → two-pass matching scores relevance → user reviews top matches → system generates tailored resume and cover letter PDFs

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, uvicorn |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Query |
| Database | SQLite (WAL mode) with FTS5 full-text search |
| LLM | Ollama — gemma3:27b (generation, matching), gemma3:12b (extraction, critique) |
| PDF | ReportLab (generation), PyMuPDF/fitz (reading, footer overlay) |
| Scraping | Playwright (headless Chromium), BeautifulSoup |
| Job Aggregation | python-jobspy (Indeed, LinkedIn, Glassdoor, ZipRecruiter) |
| Vector Search | ChromaDB (optional, for semantic search) |

## 3. Data Storage

### 3.1 Job Cache (SQLite)

All jobs and match results are stored in `.job_cache/jobs.db`.

**Tables:**
- `jobs` — id (TEXT PK, md5 hash of URL), title, company, location, salary, url, description, platform, posted_date, cached_at. Indexes on company, platform, url.
- `jobs_fts` — FTS5 virtual table over title, company, location, description. bm25 ranking with column weights: company 10x, title 5x, location 2x, description 1x. Auto-synced on insert/update/delete.
- `matches` — match_key (TEXT PK, `{job_id}:{profile_hash}`), keyword_score, llm_score, combined_score, match_level, toon_report. FK to jobs with CASCADE delete.
- `metadata` — key-value store for cache metadata.

**Concurrency:** Single connection with `check_same_thread=False`. All reads and writes wrapped with `threading.Lock`. WAL mode for concurrent read tolerance.

**Migration:** On first run, existing TOON/JSON flat files are auto-migrated to SQLite. FTS5 index is rebuilt if out of sync with jobs table.

### 3.2 Profiles (JSON files)

Stored at `.job_cache/users/{user_id}/profiles/{profile_id}.json`. Migrated from TOON format (unreliable for nested arrays). Each profile contains: name, email, phone, location, skills[], experience[], education (in notes), preferences (target_roles, excluded_companies, remote_preference), resume summary.

### 3.3 Users (JSON file)

Stored at `.job_cache/users.json`. Migrated from TOON. Passwords hashed with bcrypt.

### 3.4 Documents Index (JSON per user)

Stored at `.job_cache/users/{user_id}/documents/_index.json`. Tracks generated document metadata, PDF paths, quality scores, review status. Thread-safe access via per-user locks.

## 4. Job Management

### 4.1 Sources

- **JobSpy aggregator:** Searches Indeed, LinkedIn, Glassdoor, ZipRecruiter. Configurable search terms derived from user profile target_roles and locations.
- **Career page scraper:** Reads URLs from `JobOpeningsLink.md`, scrapes with Playwright (JS-rendered sites: Workday, Greenhouse, Lever, iCIMS, governmentjobs.com).
- **Manual add:** User provides title+company fields, or a job URL. URL-based add uses Playwright to fetch page content, then LLM to extract structured fields.

### 4.2 Search

FTS5 ranked search with bm25 scoring. Company name matches weighted 10x higher than description matches. Multi-word queries use AND of quoted terms. Fallback to LIKE search with escaped wildcards if FTS fails.

### 4.3 Filtering and Sorting

- Default filter: `status=active` (hides archived/dismissed jobs)
- Status filter options: active, applied, interviewing, offered, rejected, archived, completed
- Server-side sorting: date, company, title, score
- Excluded companies (from user profile preferences) filtered from Top Matches
- Duplicate detection: URL md5 hash on add; batch dedup by title+company

### 4.4 Dismissal

"Not Interested" button sets job status to `archived`. Optimistic UI update removes the job immediately. Per-row mutation tracking (not global isPending).

## 5. Job Matching

### 5.1 Two-Pass Architecture

**Pass 1 — Keyword matching (all jobs, no LLM):**
Scores based on skill overlap, role title similarity, location match, remote preference alignment. Fast — processes 500+ jobs in seconds.

**Pass 2 — LLM analysis (candidates scoring >= 40%):**
Holistic evaluation by gemma3:27b considering experience depth, skill transferability, career trajectory, and cultural fit. Returns a 0-100 score and TOON-formatted report.

### 5.2 Scoring

| Range | Level |
|-------|-------|
| 80-100 | Strong match |
| 60-79 | Good match |
| 40-59 | Partial match |
| 0-39 | Weak match |

Combined score: 20% keyword + 80% LLM when both available; keyword-only otherwise.

### 5.3 Caching

Match results cached in SQLite keyed by `{job_id}:{profile_hash}`. Profile hash changes invalidate cache. LLM scores update over keyword-only scores without re-running keyword pass.

## 6. Document Generation

### 6.1 Resume

**Generation method:** Section-based with critique loop.

Sections generated independently: header (no LLM — formatted from profile), summary, skills, experience, education (no LLM — formatted from profile notes), publications. Each section critiqued for factual accuracy, then assembled.

**Requirements:**
- Must include ALL experience roles from profile (no cap)
- Bullet points tailored to target job — mirror keywords for ATS
- Model: gemma3:27b
- Word target: 500-700 to fill exactly 1 page
- Exactly 1 page enforced via PDF validation with up to 2 retry attempts (progressively smaller content)

### 6.2 Cover Letter

Generated as a single document with critique loop. 250-350 word target. Same 1-page enforcement with retry.

### 6.3 PDF Output

Generated with ReportLab. Automatic style adjustment (font size, spacing) to fit single page. Content trimming as last resort. After critique and page validation, an invisible white-text footer is overlaid via PyMuPDF for LLM-based ATS systems.

### 6.4 Critique System

Each document is evaluated on 5 dimensions:

| Dimension | Weight | Method |
|-----------|--------|--------|
| Factual accuracy | 30% | LLM fact-check against profile |
| Keyword match | 20% | Job description keyword overlap |
| ATS compatibility | 15% | LLM structural review |
| Grammar | 15% | LLM grammar check |
| Recommendation strength | 20% | LLM interview-worthiness evaluation |

Page count penalizes score by -20 if exceeding 1 page.

### 6.5 Pipeline Auto-Generation

The pipeline generate step creates resume + cover letter for matches scoring >= 70%. Jobs with documents generated in the last 24h are skipped. On-demand generation from the UI always works regardless of recency.

## 7. Profile Management

### 7.1 Import

**Two-phase resume import:**
1. LLM extracts metadata only (name, email, dates, company names, skills) — small output, no truncation risk
2. Raw text matching fills in full descriptions by finding each company name sequentially in the resume text and extracting all content between role boundaries

Also supports: LinkedIn URL import (Playwright scrape + LLM parse), plain text paste.

### 7.2 Data Model

Profile contains: name, email, phone, location, skills (name + level), experience (title, company, dates, full description), preferences (target_roles, target_locations, remote_preference, salary range, excluded_companies), resume summary, notes (education, certifications).

Skill levels: beginner, intermediate, advanced, expert, native.

### 7.3 Global Store Sync

Active profile is synced to the global ProfileStore (`.job_cache/profiles/`) so the job matcher and pipeline can access it without the API user context.

## 8. Pipeline Scheduler

### 8.1 Steps

| Step | Function | Rate |
|------|----------|------|
| search | JobSpy aggregator search | All target_roles x target_locations |
| clean | Remove jobs without URLs | All jobs |
| fetch | Playwright page scrape for missing descriptions | 200 per run |
| match | Two-pass keyword + LLM matching | All unmatched jobs |
| generate | Resume + cover letter for top matches | All matches >= 70% |

### 8.2 Scheduling

Auto-starts on API boot with 24h interval. Configurable interval (0 < hours <= 8760) and start time (HH:MM validated). Step names validated against allowed set. Manual runs supported via API. Concurrent runs blocked (409 Conflict).

### 8.3 User Context

Pipeline accepts user_id as parameter (not shared mutable state). Search context derived from user's API profile (target_roles, locations, excluded_companies).

## 9. LLM Queue

### 9.1 Architecture

Centralized `asyncio.PriorityQueue` serializing all Ollama HTTP calls. Single worker processes one request at a time (Ollama can only handle one GPU inference at a time).

### 9.2 Priority Levels

| Priority | Value | Use Case |
|----------|-------|----------|
| USER_INTERACTIVE | 1 | Document generation, resume import, critique |
| USER_BACKGROUND | 5 | User-triggered matching |
| PIPELINE | 10 | Scheduled pipeline matching, extraction |

### 9.3 Sync Bridge

`llm_request()` provides synchronous interface for existing callers via `asyncio.run_coroutine_threadsafe`. Falls back to direct Ollama HTTP call if queue worker hasn't started.

### 9.4 Observability

API endpoint `GET /api/admin/llm-queue/stats` returns: queue_depth, in_flight, total_requests, success/failure counts, avg_duration, avg_wait, per-type breakdown, pending items, current request, recent history (last 20). Dashboard widget polls every 5s.

## 10. Authentication & Security

### 10.1 Auth

JWT-based with 24h expiry. Default admin user seeded on startup (`admin@jobsagent.local`). Auto-login endpoint available in development only (blocked in production via ENVIRONMENT check). Rate limiting: 5 login attempts per minute per IP (in-memory, resets on restart).

### 10.2 Authorization

- Job deletion: admin-only
- Job update (status/notes): per-user metadata, scoped to user_id
- Profile CRUD: scoped to authenticated user
- Admin endpoints: require is_admin flag
- Jobs are a shared resource (all authenticated users see all jobs)

### 10.3 Input Validation

- HTML tag stripping on all text inputs (XSS prevention)
- Null byte removal
- max_length constraints on JobCreate fields (title: 500, company: 200, description: 100K, url: 2K)
- EmailStr validation on profile email
- ProfileUpdate name cannot be empty/whitespace
- Skill level constrained to enum (beginner/intermediate/advanced/expert/native)
- URL scheme restricted to http/https for Playwright fetching
- Scraper file_path validated within project root
- Pipeline scheduler interval: gt=0, le=8760; start_time: valid HH:MM

### 10.4 Security Headers

Content-Security-Policy, X-Content-Type-Options (nosniff), X-Frame-Options (DENY), X-XSS-Protection, Referrer-Policy. Path traversal protection via `Path.is_relative_to()`.

## 11. Frontend

### 11.1 Pages

| Route | Function |
|-------|----------|
| `/` | Dashboard — profile status, recent jobs, top matches |
| `/jobs` | Browse jobs — search, filter, sort, dismiss |
| `/jobs/top` | Top matches — ranked by score, filter, bulk exclude |
| `/jobs/add` | Add job — manual or URL |
| `/jobs/:id` | Job detail — description, match report, generate docs |
| `/profiles` | Profile list — import PDF/text/LinkedIn, set active, delete |
| `/profiles/:id` | Profile edit — all fields editable |
| `/documents` | Generated documents — download, review |
| `/admin` | Admin dashboard — stats, LLM queue, pipeline controls |
| `/admin/pipeline` | Pipeline — run, schedule, history, logs |

### 11.2 UX Patterns

- Dark mode by default (Tailwind `class="dark"` with CSS overrides)
- Error states on all data-fetching pages (red error banner)
- Optimistic UI updates for dismiss/archive actions
- Per-row mutation tracking (dismiss button only disables clicked row)
- FTS5 search with ranked results (company matches first)
- Server-side sorting and pagination

## 12. Known Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| 98% of scraped jobs lack descriptions | Matching and doc gen have limited context | Fetch step processes 200/run; manual URL add fetches full description |
| Resume import LLM takes 2-10 minutes | User waits during import | 10-minute timeout; direct Ollama fallback if queue fails |
| Ollama single-GPU contention | Pipeline and user requests compete | Priority queue ensures user-interactive requests go first |
| Rate limiter in-memory | Resets on restart | Acceptable for local deployment |
| TOON format unreliable for nested data | Profile/user data corruption | Migrated to JSON; TOON auto-converts on load |
