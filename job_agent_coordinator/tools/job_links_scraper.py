"""Job Links Scraper: Scrapes job openings from a list of URLs in markdown files."""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from google.adk.tools import FunctionTool

from .job_cache import get_cache

logger = logging.getLogger(__name__)

# Configuration
DEFAULT_LINKS_FILE = Path(__file__).parent.parent.parent / "JobOpeningsLink.md"
SCRAPE_DELAY = 2  # seconds between requests
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# LLM configuration - use 12b model for faster extraction
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
SCRAPER_MODEL = os.getenv("SCRAPER_MODEL", "gemma3:12b")  # Faster model for extraction

# Sites that require JavaScript rendering (Playwright)
JS_RENDERED_SITES = [
    "governmentjobs.com",
    "workday.com",
    "myworkdayjobs.com",
    "icims.com",
    "greenhouse.io",
    "lever.co",
    "careers.honeywell.com",  # Workday-based
    "dodciviliancareers.com",
    "careers.caci.com",
    "blueorigin.com",
    "careers.rtx.com",  # Raytheon
    "jobs.baesystems.com",
]

# Check if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. JS-rendered sites won't work. pip install playwright && playwright install chromium")


def parse_markdown_links(file_path: str = None) -> List[Dict[str, str]]:
    """Parse markdown file and extract all links with their categories."""
    path = Path(file_path) if file_path else DEFAULT_LINKS_FILE
    
    if not path.exists():
        logger.error(f"Links file not found: {path}")
        return []
    
    content = path.read_text()
    links = []
    current_category = "Uncategorized"
    
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            current_category = line[3:].strip()
            continue
        
        match = re.match(r'-\s*\[([^\]]+)\]\(([^)]+)\)', line)
        if match:
            name, url = match.groups()
            links.append({
                "name": name.strip(),
                "url": url.strip(),
                "category": current_category
            })
    
    logger.info(f"📋 Parsed {len(links)} links from {path.name}")
    return links


def find_job_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Find links to additional job pages (pagination, job details, etc.)"""
    job_links = set()
    base_domain = urlparse(base_url).netloc
    
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text(strip=True).lower()
        
        # Skip empty or javascript links
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        
        # Convert to absolute URL
        full_url = urljoin(base_url, href)
        
        # Only follow links on same domain
        if urlparse(full_url).netloc != base_domain:
            continue
        
        # Check if this looks like a job-related link
        href_lower = href.lower()
        
        # Pagination links
        if any(p in href_lower for p in ["page=", "page/", "p=", "offset=", "start="]):
            job_links.add(full_url)
            continue
        
        # "View all", "See more", "Load more" links
        if any(p in text for p in ["view all", "see all", "see more", "load more", "show more", "all jobs", "more jobs"]):
            job_links.add(full_url)
            continue
        
        # Individual job links (common patterns)
        if any(p in href_lower for p in ["/job/", "/jobs/", "/position/", "/opening/", 
                                          "/career/", "/vacancy/", "jobid=", "job-id=",
                                          "/requisition/", "/posting/"]):
            job_links.add(full_url)
            continue
    
    return list(job_links)[:50]  # Limit to 50 additional links


def scrape_with_pagination(url: str, max_pages: int = 3) -> Dict[str, Any]:
    """Scrape a job page and follow pagination links."""
    all_text = []
    all_job_urls = []
    pages_scraped = 0
    
    urls_to_scrape = [url]
    scraped_urls = set()
    
    while urls_to_scrape and pages_scraped < max_pages:
        current_url = urls_to_scrape.pop(0)
        
        if current_url in scraped_urls:
            continue
        scraped_urls.add(current_url)
        
        result = scrape_webpage(current_url, follow_links=False)
        if not result:
            continue
        
        all_text.append(result["text"])
        pages_scraped += 1
        
        # Find additional job links
        if pages_scraped == 1:  # Only from first page to avoid too many requests
            try:
                response = requests.get(current_url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
                soup = BeautifulSoup(response.text, "html.parser")
                additional_links = find_job_links(soup, current_url)
                
                # Add pagination links to scrape queue
                pagination_links = [l for l in additional_links if any(p in l.lower() for p in ["page", "offset", "start"])]
                urls_to_scrape.extend(pagination_links[:2])  # Max 2 more pages
                
                # Collect individual job URLs
                job_detail_links = [l for l in additional_links if l not in pagination_links]
                all_job_urls.extend(job_detail_links)
                
                if pagination_links:
                    logger.info(f"   📑 Found {len(pagination_links)} pagination links")
                if job_detail_links:
                    logger.info(f"   🔗 Found {len(job_detail_links)} job detail links")
                    
            except Exception as e:
                logger.debug(f"Failed to find additional links: {e}")
    
    combined_text = "\n\n---PAGE BREAK---\n\n".join(all_text)
    
    return {
        "url": url,
        "text": combined_text,
        "pages_scraped": pages_scraped,
        "job_urls": all_job_urls[:30],  # Top 30 job URLs
        "scraped_at": datetime.now().isoformat(),
    }


def needs_javascript(url: str) -> bool:
    """Check if a URL requires JavaScript rendering."""
    return any(site in url.lower() for site in JS_RENDERED_SITES)


def scrape_with_playwright(url: str, wait_time: int = 3) -> Optional[Dict[str, Any]]:
    """Scrape a JavaScript-rendered page using Playwright headless browser."""
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning(f"   ⚠️ Playwright not available, falling back to requests")
        return None
    
    logger.info(f"   🎭 Using Playwright for JS-rendered page...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Navigate and wait for content to load (45s timeout for slow sites)
            page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Wait additional time for dynamic content
            page.wait_for_timeout(wait_time * 1000)
            
            # Try to click "show more" or load more buttons if present
            try:
                load_more_selectors = [
                    "button:has-text('Load More')",
                    "button:has-text('Show More')",
                    "a:has-text('View All')",
                    "[class*='load-more']",
                    "[class*='show-more']",
                ]
                for selector in load_more_selectors:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(2000)
                        logger.info(f"   📜 Clicked load more button")
                        break
            except:
                pass
            
            # Get the fully rendered HTML
            html = page.content()
            title = page.title()
            
            browser.close()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove non-content elements
            for element in soup(["script", "style", "nav", "footer", "header", "aside", 
                                "noscript", "iframe", "svg", "form", "button", "input"]):
                element.decompose()
            
            # Look for job listing containers
            job_selectors = [
                ".job-listing", ".job-item", ".job-card", ".job-row",
                "[class*='job-list']", "[class*='JobList']", 
                "[class*='posting']", "[class*='opportunity']",
                ".search-results", ".results-list",
                "table.jobs", "#job-results", "#search-results",
            ]
            
            job_content = None
            for selector in job_selectors:
                container = soup.select_one(selector)
                if container and len(container.get_text(strip=True)) > 100:
                    job_content = container
                    break
            
            if not job_content:
                # Try finding any div with multiple job-like items
                for div in soup.find_all("div"):
                    links = div.find_all("a")
                    if len(links) > 5:
                        link_texts = [l.get_text(strip=True) for l in links[:10]]
                        # Check if links look like job titles
                        if any(any(word in text.lower() for word in ["engineer", "manager", "analyst", "developer", "officer", "specialist"]) 
                               for text in link_texts):
                            job_content = div
                            break
            
            if job_content:
                text = job_content.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
            
            # Clean up excessive whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Limit text length
            max_chars = 30000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...[truncated]"
            
            logger.info(f"   🎭 Playwright extracted {len(text):,} chars")
            
            return {
                "url": url,
                "title": title,
                "text": text,
                "html": html[:50000],
                "scraped_at": datetime.now().isoformat(),
                "method": "playwright"
            }
            
    except Exception as e:
        logger.error(f"   ❌ Playwright failed: {e}")
        return None


def scrape_webpage(url: str, follow_links: bool = True) -> Optional[Dict[str, Any]]:
    """Scrape a webpage and extract job-focused text content.
    
    Automatically uses Playwright for JavaScript-rendered sites.
    """
    logger.info(f"   🌐 Fetching: {url[:60]}...")
    
    # Check if this site requires JavaScript rendering
    if needs_javascript(url):
        result = scrape_with_playwright(url)
        if result:
            return result
        logger.info(f"   ⚠️ Playwright failed, trying regular requests...")
    
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", 
                            "noscript", "iframe", "svg", "form", "button", "input"]):
            element.decompose()
        
        # Remove common boilerplate by class/id patterns
        boilerplate_patterns = [
            "cookie", "banner", "popup", "modal", "overlay", "sidebar", 
            "filter", "facet", "breadcrumb", "pagination", "social",
            "share", "newsletter", "subscribe", "advertisement", "ad-",
            "promo", "alert", "notice", "gdpr", "consent"
        ]
        for pattern in boilerplate_patterns:
            for elem in soup.find_all(class_=lambda x: x and pattern in str(x).lower()):
                elem.decompose()
            for elem in soup.find_all(id=lambda x: x and pattern in str(x).lower()):
                elem.decompose()
        
        title = soup.title.string if soup.title else "No title"
        
        # Try to find job-specific content containers
        job_content = None
        
        # Method 1: Look for common job listing containers
        job_selectors = [
            {"class_": re.compile(r"job|position|opening|career|vacancy|listing", re.I)},
            {"class_": re.compile(r"search-result|result-list|job-list", re.I)},
            {"role": "main"},
            {"id": re.compile(r"job|position|career|content|main", re.I)},
        ]
        
        for selector in job_selectors:
            containers = soup.find_all(**selector)
            if containers:
                # Get text from all matching containers
                texts = [c.get_text(separator="\n", strip=True) for c in containers]
                combined = "\n\n".join(texts)
                if len(combined) > 500:  # Minimum viable content
                    job_content = combined
                    logger.info(f"   🎯 Found job container ({len(combined):,} chars)")
                    break
        
        # Method 2: Look for lists of links (common job board pattern)
        if not job_content:
            # Find the largest list or table that might contain jobs
            for tag in ["ul", "ol", "table", "div"]:
                elements = soup.find_all(tag)
                for elem in elements:
                    text = elem.get_text(separator="\n", strip=True)
                    # Check if it looks like job listings
                    job_keywords = ["engineer", "manager", "developer", "analyst", 
                                   "designer", "director", "scientist", "lead", "senior"]
                    keyword_count = sum(1 for kw in job_keywords if kw in text.lower())
                    if keyword_count >= 3 and len(text) > 1000:
                        job_content = text
                        logger.info(f"   🎯 Found job list ({len(text):,} chars, {keyword_count} keywords)")
                        break
                if job_content:
                    break
        
        # Fallback: Use full page text but with smarter extraction
        if not job_content:
            job_content = soup.get_text(separator="\n", strip=True)
            logger.info(f"   📄 Using full page text")
        
        # Clean up the text
        lines = job_content.split("\n")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Skip very short lines (navigation items)
            if len(line) < 3:
                continue
            # Skip lines that look like navigation
            if line.lower() in ["home", "about", "contact", "login", "sign in", "menu", 
                               "search", "filter", "sort", "back", "next", "previous"]:
                continue
            # Skip lines with too many special characters (probably UI elements)
            if len(re.findall(r'[►▼▲◄→←|•●○]', line)) > 2:
                continue
            cleaned_lines.append(line)
        
        text = "\n".join(cleaned_lines)
        
        # Increased limit since we have cleaner text now
        max_chars = 25000
        if len(text) > max_chars:
            text = text[:max_chars] + "\n...[truncated]"
        
        logger.info(f"   ✅ Extracted {len(text):,} chars (cleaned)")
        
        return {
            "url": url,
            "title": title,
            "text": text,
            "scraped_at": datetime.now().isoformat(),
        }
        
    except requests.RequestException as e:
        logger.error(f"   ❌ Scrape failed: {e}")
        return None


def extract_jobs_with_llm(
    scraped_data: Dict[str, Any],
    source_name: str,
    category: str
) -> List[Dict[str, Any]]:
    """Use LLM (gemma3:12b) to extract job listings from scraped content."""
    
    logger.info(f"   🤖 Extracting jobs with {SCRAPER_MODEL}...")
    
    # Shorter, more focused prompt for better JSON output
    prompt = f"""Extract job titles and locations from this {source_name} careers page.

PAGE CONTENT (truncated):
{scraped_data['text'][:8000]}

Output a JSON array. Each object needs: title, location.
Keep it short. Example: [{{"title":"Software Engineer","location":"Seattle, WA"}}]

JSON array:"""

    try:
        start = time.time()
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": SCRAPER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 2500}
            },
            timeout=120
        )
        response.raise_for_status()
        elapsed = time.time() - start
        
        result = response.json().get("response", "[]")
        
        # Try to extract valid JSON array - be more lenient
        jobs = []
        
        # Method 1: Find complete JSON array
        json_match = re.search(r'\[[\s\S]*\]', result)
        if json_match:
            try:
                jobs = json.loads(json_match.group())
            except json.JSONDecodeError:
                # Method 2: Try to fix incomplete JSON
                json_str = json_match.group()
                # Try to close incomplete arrays/objects
                if not json_str.rstrip().endswith(']'):
                    # Find last complete object
                    last_brace = json_str.rfind('}')
                    if last_brace > 0:
                        json_str = json_str[:last_brace+1] + ']'
                        try:
                            jobs = json.loads(json_str)
                        except:
                            pass
        
        if not jobs:
            # Method 3: Parse line by line for job titles
            lines = scraped_data['text'].split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line) > 10 and len(line) < 100:
                    # Look for job-like titles
                    if any(kw in line.lower() for kw in ['engineer', 'manager', 'director', 'analyst', 'developer', 'scientist', 'lead', 'architect']):
                        jobs.append({"title": line, "location": "Not specified"})
                        if len(jobs) >= 30:
                            break
        
        # Enrich jobs with metadata
        for job in jobs:
            if isinstance(job, dict):
                job["source_name"] = source_name
                job["source_category"] = category
                job["source_url"] = scraped_data["url"]
                job["extracted_at"] = datetime.now().isoformat()
                job["platform"] = "scraped"
                job["company"] = job.get("company", source_name)
                job.setdefault("location", "Not specified")
                job.setdefault("salary", "Not disclosed")
                job.setdefault("job_url", scraped_data["url"])
        
        # Filter out invalid entries
        jobs = [j for j in jobs if isinstance(j, dict) and j.get("title")]
        
        logger.info(f"   📊 Extracted {len(jobs)} jobs in {elapsed:.1f}s")
        
        # Log each job found
        for job in jobs[:10]:
            title = str(job.get('title') or 'Unknown')[:45]
            location = str(job.get('location') or 'N/A')[:20]
            logger.info(f"      → {title} | {location}")
        if len(jobs) > 10:
            logger.info(f"      ... and {len(jobs) - 10} more")
        
        return jobs
            
    except json.JSONDecodeError as e:
        logger.error(f"   ❌ JSON parse error: {e}")
        return []
    except requests.RequestException as e:
        logger.error(f"   ❌ LLM request failed: {e}")
        return []


def check_duplicate_with_llm(new_job: Dict, existing_jobs: List[Dict]) -> Optional[str]:
    """
    Use LLM to determine if a job is a duplicate of existing jobs.
    
    Returns:
        job_id of duplicate if found, None otherwise
    """
    if not existing_jobs:
        return None
    
    # Quick pre-filter: same company, similar title
    new_title = new_job.get("title", "").lower()
    new_company = new_job.get("company", "").lower()
    
    candidates = []
    for job in existing_jobs:
        existing_title = job.get("title", "").lower()
        existing_company = job.get("company", "").lower()
        
        # Same company and title starts similarly
        if existing_company == new_company:
            # Check title similarity
            if new_title == existing_title:
                return job.get("id")  # Exact match
            
            # Similar enough to check with LLM
            words_new = set(new_title.split())
            words_existing = set(existing_title.split())
            overlap = len(words_new & words_existing) / max(len(words_new), 1)
            
            if overlap > 0.5:
                candidates.append(job)
    
    # If no candidates, not a duplicate
    if not candidates:
        return None
    
    # Use LLM for fuzzy matching (only for close candidates)
    candidates_str = "\n".join([
        f"- ID:{c.get('id', 'unknown')[:8]} | {c.get('title')} | {c.get('company')} | {c.get('location')}"
        for c in candidates[:5]
    ])
    
    prompt = f"""Is this job posting a duplicate of any existing job?

NEW JOB:
Title: {new_job.get('title')}
Company: {new_job.get('company')}
Location: {new_job.get('location')}

EXISTING JOBS:
{candidates_str}

If the new job is a duplicate (same position, same company, same/similar location), respond with ONLY the ID of the duplicate.
If NOT a duplicate, respond with ONLY the word "NONE".

Response:"""

    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": SCRAPER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 50}
            },
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json().get("response", "").strip().upper()
        
        if result == "NONE" or not result:
            return None
        
        # Extract ID from response
        for candidate in candidates:
            if candidate.get("id", "")[:8] in result:
                return candidate.get("id")
        
        return None
        
    except Exception as e:
        logger.debug(f"Duplicate check failed: {e}")
        return None


def cache_jobs_with_dedup(jobs: List[Dict], use_llm_dedup: bool = True) -> Dict[str, int]:
    """
    Cache jobs with deduplication.
    
    Returns:
        Dict with 'added', 'duplicates', 'total'
    """
    cache = get_cache()
    existing_jobs = list(cache._jobs.values()) if use_llm_dedup else []
    
    added = 0
    duplicates = 0
    
    for job in jobs:
        # Check for duplicates
        if use_llm_dedup and existing_jobs:
            dup_id = check_duplicate_with_llm(job, existing_jobs)
            if dup_id:
                logger.debug(f"   🔄 Duplicate skipped: {job.get('title', 'Unknown')[:30]}")
                duplicates += 1
                continue
        
        # Add to cache
        if cache.add(job):
            added += 1
            existing_jobs.append(job)  # Add to existing for subsequent checks
    
    if added > 0:
        cache._save_jobs()
    
    return {"added": added, "duplicates": duplicates, "total": len(jobs)}


def scrape_job_links(
    file_path: str = None,
    categories: str = "",
    max_sources: int = 0,
    cache_results: bool = True,
    use_llm_dedup: bool = False,  # Disabled by default (slower)
    follow_pagination: bool = True,  # Follow pagination links
    max_pages_per_source: int = 3,  # Max pages to scrape per source
    delay_seconds: float = SCRAPE_DELAY
) -> Dict[str, Any]:
    """
    Scrape job openings from all links in a markdown file.
    
    ⚠️ WARNING: This tool is SLOW and resource-intensive. Use parsimoniously!
    - Full scrape of all sources: 10-20 minutes
    - Single category: 2-5 minutes
    - Uses LLM for extraction (tokens consumed per source)
    - Consider using get_links_summary first to see available sources
    
    Args:
        file_path: Path to markdown file with job links
        categories: Comma-separated categories to scrape (empty = all). Use this to limit scope!
        max_sources: Maximum sources to scrape (0 = all). Set a limit to reduce time!
        cache_results: Whether to cache extracted jobs
        use_llm_dedup: Use LLM for duplicate detection (slower but smarter)
        follow_pagination: Follow pagination links to get more jobs
        max_pages_per_source: Max pages to scrape per source
        delay_seconds: Delay between requests
    
    Returns:
        Dict with scraping results and statistics
    """
    start_time = time.time()
    
    all_links = parse_markdown_links(file_path)
    if not all_links:
        return {"success": False, "error": "No links found", "jobs_found": 0}
    
    # Filter by categories
    if categories:
        filter_cats = [c.strip().lower() for c in categories.split(",")]
        all_links = [l for l in all_links if l["category"].lower() in filter_cats]
        logger.info(f"🔍 Filtered to {len(all_links)} sources in: {categories}")
    
    if max_sources > 0:
        all_links = all_links[:max_sources]
    
    logger.info(f"🚀 Starting scrape of {len(all_links)} sources (pagination={'on' if follow_pagination else 'off'})")
    logger.info("=" * 60)
    
    all_jobs = []
    all_job_urls = []  # Collect individual job URLs for potential future scraping
    successful_sources = []
    failed_sources = []
    total_added = 0
    total_duplicates = 0
    
    for i, link in enumerate(all_links):
        logger.info(f"\n[{i+1}/{len(all_links)}] 📡 {link['name']} ({link['category']})")
        
        # Use pagination if enabled
        if follow_pagination:
            scraped = scrape_with_pagination(link["url"], max_pages=max_pages_per_source)
            if scraped and scraped.get("job_urls"):
                all_job_urls.extend(scraped["job_urls"])
        else:
            scraped = scrape_webpage(link["url"])
        
        if scraped:
            jobs = extract_jobs_with_llm(scraped, link["name"], link["category"])
            
            if jobs:
                all_jobs.extend(jobs)
                successful_sources.append({
                    "name": link["name"],
                    "category": link["category"],
                    "jobs_found": len(jobs)
                })
                
                # Cache with deduplication
                if cache_results:
                    result = cache_jobs_with_dedup(jobs, use_llm_dedup=use_llm_dedup)
                    total_added += result["added"]
                    total_duplicates += result["duplicates"]
                    logger.info(f"   💾 Cached: {result['added']} new, {result['duplicates']} duplicates")
            else:
                failed_sources.append({"name": link["name"], "reason": "No jobs extracted"})
        else:
            failed_sources.append({"name": link["name"], "reason": "Scrape failed"})
        
        if i < len(all_links) - 1:
            time.sleep(delay_seconds)
    
    elapsed = time.time() - start_time
    
    # Generate summary
    summary = _generate_summary(all_jobs, successful_sources, failed_sources, elapsed, total_added, total_duplicates)
    toon_report = _generate_scrape_report_toon(all_jobs, successful_sources, failed_sources, elapsed)
    
    logger.info("\n" + "=" * 60)
    logger.info(summary)
    logger.info("=" * 60)
    
    return {
        "success": True,
        "jobs_found": len(all_jobs),
        "jobs_cached": total_added,
        "duplicates_skipped": total_duplicates,
        "sources_scraped": len(successful_sources),
        "sources_failed": len(failed_sources),
        "job_detail_urls": len(all_job_urls),  # Count of individual job URLs found
        "elapsed_seconds": round(elapsed, 1),
        "summary": summary,
        "toon_report": toon_report,
        "successful_sources": successful_sources,
        "failed_sources": failed_sources,
    }


def _generate_summary(
    jobs: List[Dict],
    successful: List[Dict],
    failed: List[Dict],
    elapsed: float,
    added: int,
    duplicates: int
) -> str:
    """Generate a human-readable summary of scraping results."""
    lines = [
        f"🎯 SCRAPE SUMMARY",
        f"   Total jobs found: {len(jobs)}",
        f"   Jobs cached (new): {added}",
        f"   Duplicates skipped: {duplicates}",
        f"   Sources scraped: {len(successful)}",
        f"   Sources failed: {len(failed)}",
        f"   Time elapsed: {elapsed:.1f}s ({elapsed/60:.1f} min)",
    ]
    
    if jobs:
        # Top categories
        cat_counts = {}
        for job in jobs:
            cat = job.get("source_category", "Unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
        lines.append(f"\n   📁 By Category:")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"      • {cat}: {count} jobs")
        
        # Top companies
        company_counts = {}
        for job in jobs:
            company = job.get("company", "Unknown")
            company_counts[company] = company_counts.get(company, 0) + 1
        
        lines.append(f"\n   🏢 Top Companies:")
        for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"      • {company}: {count} jobs")
    
    return "\n".join(lines)


def _generate_scrape_report_toon(
    jobs: List[Dict],
    successful: List[Dict],
    failed: List[Dict],
    elapsed: float
) -> str:
    """Generate TOON formatted scraping report."""
    lines = []
    
    lines.append("[scrape_report]")
    lines.append(f"total_jobs: {len(jobs)}")
    lines.append(f"sources_scraped: {len(successful)}")
    lines.append(f"sources_failed: {len(failed)}")
    lines.append(f"elapsed_seconds: {round(elapsed, 1)}")
    lines.append(f"timestamp: {datetime.now().isoformat()}")
    lines.append("")
    
    lines.append("[successful_sources]")
    for src in successful:
        lines.append(f"- {src['name']}: {src['jobs_found']} jobs ({src['category']})")
    lines.append("")
    
    if failed:
        lines.append("[failed_sources]")
        for src in failed:
            lines.append(f"- {src['name']}: {src['reason']}")
        lines.append("")
    
    cat_counts = {}
    for job in jobs:
        cat = job.get("source_category", "Unknown")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    
    lines.append("[jobs_by_category]")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        lines.append(f"- {cat}: {count}")
    lines.append("")
    
    company_counts = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        company_counts[company] = company_counts.get(company, 0) + 1
    
    lines.append("[top_companies]")
    for company, count in sorted(company_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"- {company}: {count}")
    lines.append("")
    
    lines.append("[sample_jobs]")
    for job in jobs[:5]:
        lines.append(f"- {job.get('title', 'Unknown')} @ {job.get('company', 'Unknown')}")
        lines.append(f"  location: {job.get('location', 'N/A')}")
    
    return "\n".join(lines)


def get_links_summary(file_path: str = None) -> Dict[str, Any]:
    """Get summary of links in the markdown file without scraping."""
    links = parse_markdown_links(file_path)
    
    categories = {}
    for link in links:
        cat = link["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(link["name"])
    
    toon_lines = ["[job_links_summary]"]
    toon_lines.append(f"total_sources: {len(links)}")
    toon_lines.append(f"categories: {len(categories)}")
    toon_lines.append("")
    
    for cat, sources in categories.items():
        toon_lines.append(f"[{cat.lower().replace(' ', '_')}]")
        toon_lines.append(f"count: {len(sources)}")
        for src in sources:
            toon_lines.append(f"- {src}")
        toon_lines.append("")
    
    return {
        "success": True,
        "total_sources": len(links),
        "categories": {cat: len(sources) for cat, sources in categories.items()},
        "links": links,
        "toon_report": "\n".join(toon_lines)
    }


def scrape_single_source(
    source_name: str,
    file_path: str = None,
    cache_results: bool = True,
    use_llm_dedup: bool = False
) -> Dict[str, Any]:
    """
    Scrape jobs from a single source by name.
    
    ⚠️ NOTE: Takes 10-60 seconds per source (web scraping + LLM extraction).
    Use get_links_summary first to see available source names.
    
    Args:
        source_name: Name of source to scrape (e.g., "Boeing", "Anthropic")
        file_path: Path to markdown file with job links
        cache_results: Whether to cache extracted jobs
        use_llm_dedup: Use LLM for duplicate detection (slower)
    
    Returns:
        Dict with jobs found and caching results
    """
    links = parse_markdown_links(file_path)
    
    source_lower = source_name.lower()
    matching = [l for l in links if source_lower in l["name"].lower()]
    
    if not matching:
        return {
            "success": False,
            "error": f"Source '{source_name}' not found",
            "available_sources": [l["name"] for l in links]
        }
    
    link = matching[0]
    logger.info(f"📡 Scraping: {link['name']} ({link['category']})")
    
    scraped = scrape_webpage(link["url"])
    if not scraped:
        return {"success": False, "error": f"Failed to scrape {link['name']}"}
    
    jobs = extract_jobs_with_llm(scraped, link["name"], link["category"])
    
    added = 0
    duplicates = 0
    if cache_results and jobs:
        result = cache_jobs_with_dedup(jobs, use_llm_dedup=use_llm_dedup)
        added = result["added"]
        duplicates = result["duplicates"]
        logger.info(f"💾 Cached: {added} new, {duplicates} duplicates")
    
    return {
        "success": True,
        "source": link["name"],
        "category": link["category"],
        "url": link["url"],
        "jobs_found": len(jobs),
        "jobs_cached": added,
        "duplicates_skipped": duplicates,
        "jobs": jobs,
    }


# Create FunctionTools
scrape_job_links_tool = FunctionTool(func=scrape_job_links)
get_links_summary_tool = FunctionTool(func=get_links_summary)
scrape_single_source_tool = FunctionTool(func=scrape_single_source)
parse_markdown_links_tool = FunctionTool(func=parse_markdown_links)
