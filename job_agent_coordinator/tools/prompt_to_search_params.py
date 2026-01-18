"""Prompt to search params parser - uses Ollama to extract search parameters."""

import os
import json
import logging
import time

import httpx
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_PARSER_MODEL", "gemma3:12b")


def prompt_to_search_params(prompt: str) -> dict:
    """Parse natural language prompt into JobSpy search parameters."""
    start = time.time()
    logger.info(f"🔍 Parsing: '{prompt}' (model={OLLAMA_MODEL})")
    
    system_prompt = """Extract job search parameters. Return JSON only:
{"search_term": "job title", "location": "city, state or remote", "exclude_companies": "comma,separated", "results_wanted": 10}"""

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{OLLAMA_BASE_URL}/api/chat", json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                "stream": False, "format": "json"
            })
        
        if resp.status_code != 200:
            logger.error(f"❌ Ollama error: {resp.status_code}")
            return _fallback(prompt)
        
        content = resp.json().get("message", {}).get("content", "{}")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            import re
            m = re.search(r'\{[^{}]*\}', content)
            parsed = json.loads(m.group()) if m else {}
        
        params = {
            "search_term": parsed.get("search_term", ""),
            "location": parsed.get("location", "United States"),
            "exclude_companies": parsed.get("exclude_companies", ""),
            "results_wanted": int(parsed.get("results_wanted", 10)),
            "hours_old": 168,
            "sites": "indeed,linkedin"
        }
        
        if not params["search_term"]:
            return _fallback(prompt)
        
        elapsed = time.time() - start
        logger.info(f"✅ Parsed in {elapsed:.1f}s: term='{params['search_term']}' loc='{params['location']}'")
        return {"success": True, "params": params, "parse_time": elapsed}
        
    except httpx.ConnectError:
        logger.error("❌ Cannot connect to Ollama")
        return _fallback(prompt)
    except Exception as e:
        logger.error(f"❌ Parse error: {e}")
        return _fallback(prompt)


def _fallback(prompt: str) -> dict:
    """Simple fallback parser."""
    logger.info("🔄 Fallback parser")
    p = prompt.lower()
    
    loc = "United States"
    for kw, l in [("seattle", "Seattle, WA"), ("san francisco", "San Francisco, CA"), 
                  ("new york", "New York, NY"), ("remote", "remote"), ("austin", "Austin, TX")]:
        if kw in p:
            loc = l
            break
    
    term = p
    for w in ["find", "search", "look for", "jobs", "positions", "roles", "in", loc.lower()]:
        term = term.replace(w, "")
    term = " ".join(term.split()).strip() or "software engineer"
    
    return {"success": True, "params": {"search_term": term, "location": loc, "exclude_companies": "",
            "results_wanted": 10, "hours_old": 168, "sites": "indeed,linkedin"}, "fallback": True}


prompt_to_search_params_tool = FunctionTool(func=prompt_to_search_params)
