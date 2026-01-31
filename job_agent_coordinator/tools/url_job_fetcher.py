"""
URL Job Fetcher: Fetch and extract job details from any job posting URL.

Supports Indeed, LinkedIn, Glassdoor, and other job boards using Playwright
for JavaScript rendering and LLM for structured data extraction.
"""

import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# LLM configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
SCRAPER_MODEL = os.getenv("SCRAPER_MODEL", "gemma3:12b")

# Browser configuration
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Check if Playwright is available
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Install with: pip install playwright && playwright install chromium")


def fetch_page_with_playwright(url: str, wait_time: int = 3) -> Optional[Dict[str, Any]]:
    """
    Fetch a page using Playwright headless browser.
    
    Args:
        url: The URL to fetch
        wait_time: Seconds to wait for dynamic content
    
    Returns:
        Dict with 'text', 'html', 'title' or None if failed
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available. Cannot fetch job page.")
        return None
    
    logger.info(f"🎭 Fetching page with Playwright...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            
            # Navigate with extended timeout for slow job boards
            page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Wait for dynamic content
            page.wait_for_timeout(wait_time * 1000)
            
            # Try to expand "show more" sections common on job boards
            try:
                expand_selectors = [
                    "button:has-text('Show more')",
                    "button:has-text('See more')",
                    "button:has-text('Read more')",
                    "[class*='show-more']",
                    "[class*='expand']",
                    "[aria-label*='expand']",
                ]
                for selector in expand_selectors:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(1000)
                        logger.info(f"   📜 Expanded content section")
                        break
            except:
                pass
            
            # Get rendered content
            html = page.content()
            title = page.title()
            
            browser.close()
            
            # Parse and clean HTML
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove non-content elements
            for element in soup(["script", "style", "nav", "footer", "header", 
                                "aside", "noscript", "iframe", "svg", "form"]):
                element.decompose()
            
            # Try to find the main job content container
            job_content = None
            job_selectors = [
                # Indeed
                "#jobDescriptionText", ".jobsearch-JobComponent-description",
                # LinkedIn
                ".show-more-less-html__markup", ".description__text",
                # Glassdoor
                ".desc", ".jobDescriptionContent",
                # Greenhouse
                "#content", ".job-post-content",
                # Lever
                ".posting-page", ".section-wrapper",
                # Workday
                "[data-automation-id='jobPostingDescription']",
                # Generic
                ".job-description", "#job-description", "[class*='job-desc']",
                ".description", "#description", "article", "main", "[role='main']",
            ]
            
            for selector in job_selectors:
                container = soup.select_one(selector)
                if container and len(container.get_text(strip=True)) > 200:
                    job_content = container
                    logger.info(f"   🎯 Found job content container")
                    break
            
            if job_content:
                text = job_content.get_text(separator="\n", strip=True)
            else:
                # Fallback to body text
                text = soup.get_text(separator="\n", strip=True)
            
            # Clean up excessive whitespace
            text = re.sub(r'\n{3,}', '\n\n', text)
            
            # Limit length
            max_chars = 25000
            if len(text) > max_chars:
                text = text[:max_chars] + "\n...[truncated]"
            
            logger.info(f"   ✅ Extracted {len(text):,} chars")
            
            return {
                "url": url,
                "title": title,
                "text": text,
                "html": html[:50000],
                "fetched_at": datetime.now().isoformat(),
            }
            
    except Exception as e:
        logger.error(f"❌ Playwright fetch failed: {e}")
        return None


def extract_job_with_llm(page_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Use LLM to extract structured job data from page content.
    
    Args:
        page_data: Dict with 'text', 'url', 'title' from page fetch
    
    Returns:
        Dict with extracted job fields or None if extraction failed
    """
    logger.info(f"🤖 Extracting job details with {SCRAPER_MODEL}...")
    
    prompt = f"""Extract job posting details from this page content.

PAGE URL: {page_data.get('url', '')}
PAGE TITLE: {page_data.get('title', '')}

PAGE CONTENT:
{page_data['text'][:12000]}

Extract the following fields and return as valid JSON:
{{
    "title": "exact job title",
    "company": "company name",
    "location": "job location (city, state or Remote)",
    "salary": "salary range if mentioned, otherwise 'Not disclosed'",
    "description": "full job description including responsibilities and requirements (preserve formatting, include bullet points)"
}}

Important:
- Extract the COMPLETE job description including all responsibilities, requirements, and qualifications
- Preserve bullet points and formatting in the description
- If a field is not found, use reasonable defaults
- Return ONLY valid JSON, no other text

JSON:"""

    try:
        start = time.time()
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": SCRAPER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 4000}
            },
            timeout=120
        )
        response.raise_for_status()
        elapsed = time.time() - start
        
        result = response.json().get("response", "{}")
        
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', result)
        if not json_match:
            logger.error("No JSON found in LLM response")
            return None
        
        import json
        job_data = json.loads(json_match.group())
        
        # Add URL and metadata
        job_data["url"] = page_data.get("url", "")
        job_data["extracted_at"] = datetime.now().isoformat()
        job_data["platform"] = "url_fetch"
        
        # Validate required fields
        if not job_data.get("title"):
            logger.error("Missing required field: title")
            return None
        if not job_data.get("company"):
            # Try to extract from page title
            page_title = page_data.get("title", "")
            if " at " in page_title:
                job_data["company"] = page_title.split(" at ")[-1].split(" - ")[0].strip()
            elif " - " in page_title:
                job_data["company"] = page_title.split(" - ")[1].strip()
            else:
                job_data["company"] = "Unknown Company"
        if not job_data.get("description"):
            # Use page text as fallback description
            job_data["description"] = page_data["text"][:5000]
        
        # Set defaults for optional fields
        job_data.setdefault("location", "Not specified")
        job_data.setdefault("salary", "Not disclosed")
        
        logger.info(f"   ✅ Extracted job in {elapsed:.1f}s")
        logger.info(f"      Title: {job_data['title'][:50]}")
        logger.info(f"      Company: {job_data['company']}")
        logger.info(f"      Location: {job_data['location']}")
        
        return job_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        return None
    except requests.RequestException as e:
        logger.error(f"❌ LLM request failed: {e}")
        return None


def fetch_job_from_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch job details from a URL using Playwright + LLM extraction.
    
    This is the main entry point for URL-based job fetching.
    
    Args:
        url: The job posting URL (Indeed, LinkedIn, Glassdoor, etc.)
    
    Returns:
        Dict with job details:
        {
            "title": str,
            "company": str,
            "location": str,
            "description": str,
            "url": str,
            "salary": str (optional),
            "extracted_at": str,
            "platform": "url_fetch"
        }
        
        Returns None if fetching or extraction fails.
    
    Example:
        >>> job = fetch_job_from_url("https://www.indeed.com/viewjob?jk=abc123")
        >>> print(job["title"], "@", job["company"])
    """
    if not url:
        logger.error("URL is required")
        return None
    
    # Validate URL
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        logger.error(f"Invalid URL: {url}")
        return None
    
    logger.info(f"📋 Fetching job from: {url[:80]}...")
    
    # Step 1: Fetch page content
    page_data = fetch_page_with_playwright(url)
    if not page_data:
        logger.error("Failed to fetch page content")
        return None
    
    # Step 2: Extract job details with LLM
    job_data = extract_job_with_llm(page_data)
    if not job_data:
        logger.error("Failed to extract job details")
        return None
    
    return job_data


def detect_job_site(url: str) -> str:
    """Detect which job site the URL is from."""
    domain = urlparse(url).netloc.lower()
    
    if "indeed" in domain:
        return "indeed"
    elif "linkedin" in domain:
        return "linkedin"
    elif "glassdoor" in domain:
        return "glassdoor"
    elif "greenhouse" in domain:
        return "greenhouse"
    elif "lever" in domain:
        return "lever"
    elif "workday" in domain or "myworkdayjobs" in domain:
        return "workday"
    else:
        return "other"
