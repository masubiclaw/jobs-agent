# Job Search Multi-Agent Orchestration System

AI-driven multi-agent system for job search, profile analysis, resume optimization, and career intelligence. **Now with PDF generation!**

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Job Agent Coordinator                                │
│                     (Main Orchestration Agent)                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
    ┌───────────┬───────────┬───────┼───────┬───────────┬───────────┐
    │           │           │       │       │           │           │
    ▼           ▼           ▼       ▼       ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Profile │ │ App     │ │Enhanced │ │ Market  │ │ Company │ │  Job    │ │ History │
│ Analyst │ │Designer │ │  Job    │ │ Analyst │ │Research │ │Posting  │ │ Manager │
│  💾     │ │ 📄💾    │ │ Search  │ │         │ │  (MCP)  │ │ Analyst │ │💾Vector │
└─────────┘ └─────────┘ └────┬────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘
                             │
  ╔══════════════════════════╧══════════════════════════════╗
  ║        ENHANCED JOB SEARCH WORKFLOW (Sequential)        ║
  ╠═════════════════════════════════════════════════════════╣
  ║  1. 🔍 PARALLEL PLATFORM SEARCH                         ║
  ║     ┌─────────┬─────────┬─────────┐                     ║
  ║     │LinkedIn │ Indeed  │Glassdoor│ (via Google/Apify)  ║
  ║     │ search  │ (Apify) │ (Apify) │                     ║
  ║     └─────────┴─────────┴─────────┘                     ║
  ║                        ↓                                ║
  ║  2. 🔄 SEARCH RESULTS AGGREGATOR                        ║
  ║     • Validate links • Apply exclusions • Deduplicate   ║
  ║                        ↓                                ║
  ║  3. ⚡ PARALLEL JOB ANALYSIS (simultaneous)             ║
  ║     ┌────────────────┐    ┌────────────────┐            ║
  ║     │ Job Posting    │    │ Company        │            ║
  ║     │ Analysis       │◄──►│ Research       │            ║
  ║     └────────────────┘    └────────────────┘            ║
  ║                        ↓                                ║
  ║  4. 🎯 ANALYSIS SYNTHESIZER                             ║
  ║     • Profile comparison • Selling points • Rankings    ║
  ╚═════════════════════════════════════════════════════════╝
```

## Sub-Agents

| Agent | Description | Storage 💾 | PDF 📄 |
|-------|-------------|-----------|--------|
| **Profile Analyst** | Skills extraction, gap analysis, career mapping | `user_profiles` | - |
| **Application Designer** | Parallel resume + cover letter with PDF output | `resume_versions`, `cover_letters`, `resume_templates`, `design_instructions` | ✅ |
| **Job Posting Analyst** | Requirements, red flags, fit scoring | - | - |
| **Market Analyst** | Salary trends, demand analysis, industry outlook | - | - |
| **Company Researcher** | Ratings, values, culture via Glassdoor MCP | - | - |
| **Search Aggregator** | Link validation, exclusions, deduplication | - | - |
| **Analysis Synthesizer** | Profile-based selling points, interview tips | Uses `user_profiles` | - |
| **History Manager** | Central vector DB for all storage | All collections | - |

### Application Designer 📄💾

```
┌─────────────────────────────────────────────────────────────┐
│              Application Designer Agent                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    PARALLEL    ┌────────────────────┐     │
│  │ Resume       │◄──────────────►│ Cover Letter       │     │
│  │ Writer 📄    │                │ Writer 📄          │     │
│  └──────────────┘                └────────────────────┘     │
├─────────────────────────────────────────────────────────────┤
│  🛡️ GUARD RAILS (Truthfulness Verification)                 │
│     • Never fabricates experiences or skills                │
│     • All claims traced to source profile                   │
│     • [NEEDS VERIFICATION] / [ESTIMATED] markers            │
│     • Truthfulness audit in output                          │
├─────────────────────────────────────────────────────────────┤
│  📄 PDF GENERATION                                          │
│     • Professional resume PDFs                              │
│     • Cover letter PDFs                                     │
│     • Template presets (professional/compact/leadership)    │
├─────────────────────────────────────────────────────────────┤
│  💾 Storage: resume_versions, cover_letters,                │
│              resume_templates, design_instructions          │
└─────────────────────────────────────────────────────────────┘
```

**Guard Rails:** Never fabricates • Source-traced claims • `[ESTIMATED]` markers • Truthfulness audit

### Analysis Synthesizer Output

```
╔══════════════════════════════════════════════════════════════════╗
║ #1: ML Engineer @ TechCorp                    Overall: 92/100    ║
╠──────────────────────────────────────────────────────────────────╣
║ 📊 Skills: 95% | Experience: 88% | Values: 90%                   ║
║ 🌟 SELLING POINTS: [Your achievements matching this role]        ║
║ 💬 INTERVIEW TIPS: [Specific stories to share]                   ║
║ ⚠️ GAPS: [Missing skill] → [How to address]                      ║
╚══════════════════════════════════════════════════════════════════╝
```

## Quick Start

```bash
cd job-search-agent
uv sync

# Web UI
adk web .

# CLI
adk run job_agent_coordinator
```

### Example Queries

```
"Find senior ML engineer jobs in San Francisco"     # Full search + analysis
"Analyze my profile: [paste resume]"                # Profile analysis (saved 💾)
"Create application for Data Scientist at Google"  # Resume + cover letter
"Generate PDF resume for Software Engineer role"   # Creates downloadable PDF 📄
"Research Amazon - culture and values"             # Company research
"Save this search as 'Remote ML Jobs'"             # Save search criteria
```

## PDF Generation 📄

The Application Designer can generate professional PDFs for resumes and cover letters.

### Features
- **Resume PDFs** - Professional formatting with customizable templates
- **Cover Letter PDFs** - Business letter format
- **Template Presets** - `professional`, `compact`, `leadership`, `technical`
- **Auto-dated Filenames** - `Name_Resume_01072026.pdf`

### PDF Location
Generated PDFs are saved to: `~/.job_agent_coordinator/generated_pdfs/`

### Template Customization
```
"Create a technical resume for backend engineer"   # Uses technical template
"Generate a leadership-focused resume as PDF"      # Uses leadership template
```

## MCP Integration

| Priority | MCP | Platforms |
|----------|-----|-----------|
| 1️⃣ | **Apify** (token) | Glassdoor jobs/company, Indeed |
| 2️⃣ | **Google Search** | Fallback for all platforms |

```bash
# Set Apify token for job search MCPs
export APIFY_API_TOKEN=your-token
```

## Storage (ChromaDB)

| Collection | Purpose |
|------------|---------|
| `user_profiles` | Profile data for job matching |
| `resume_versions` | Resume versions with descriptors |
| `cover_letters` | Cover letters by company/role |
| `resume_templates` | Formatting templates & styles |
| `design_instructions` | Guard rails & requirements |
| `job_postings` | Analyzed job postings |
| `company_analyses` | Cached company research |
| `search_criteria` | Saved search filters |

**Location:** `~/.job_agent_coordinator/history/`

### Storage by Agent

| Agent | Collections Used |
|-------|-----------------|
| Profile Analyst | `user_profiles` |
| Application Designer | `resume_versions`, `cover_letters`, `resume_templates`, `design_instructions` |
| History Manager | All collections |
| Analysis Synthesizer | Reads `user_profiles` |

## Tools Summary

### PDF Tools (Application Designer)
| Tool | Description |
|------|-------------|
| `generate_resume_pdf` | Create professional resume PDF |
| `generate_cover_letter_pdf` | Create cover letter PDF |
| `list_pdfs` | List all generated PDFs |
| `check_pdf_available` | Verify ReportLab installed |
| `get_template_presets` | Get formatting templates |

### History Tools (25+ tools)
| Category | Tools |
|----------|-------|
| User Profiles | save, get, list, update, delete, search |
| Resume Versions | save, get master, list, search |
| Cover Letters | save, get by company, search, recent |
| Resume Templates | save, get, list, delete |
| Design Instructions | save, get active, get guard rails, toggle, delete |
| Search Criteria | save, get, list, update, delete, use |

## References

- [+115% Interview Boost - Forbes](https://www.forbes.com/sites/rachelwells/2025/09/03/this-resume-hack-boosts-interview-chances-by-115-study-shows/)
- [+96% Hiring Boost - Forbes](https://www.forbes.com/sites/rachelwells/2025/04/30/this-boosts-your-chances-of-getting-hired-by-96-new-study-finds/)
- [+71% Interview Boost - Forbes](https://www.forbes.com/sites/niallmccarthy/2019/03/29/study-a-comprehensive-linkedin-profile-gives-a-71-higher-chance-of-a-job-interview-infographic/)

## License

Apache License 2.0
