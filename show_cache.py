#!/usr/bin/env python3
"""Quick script to view job cache contents."""

import json
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress logging noise
import logging
logging.disable(logging.WARNING)

from job_agent_coordinator.sub_agents.history_manager.vector_store import get_vector_store


def show_cache(cache_type: str = None, limit: int = 20):
    """Show cached items."""
    store = get_vector_store()
    
    print("=" * 70)
    print("📦 JOB AGENT CACHE")
    print("=" * 70)
    
    if not store.client:
        print("⚠️  Using in-memory storage (ChromaDB not available)")
        return
    
    # Get cache stats
    stats = store.get_cache_stats()
    print(f"\n📊 Cache Statistics:")
    print(f"   Total entries: {stats.get('total_entries', 0)}")
    print(f"   By type: {stats.get('by_type', {})}")
    print()
    
    # Get cached items
    try:
        where_filter = {"cache_type": cache_type} if cache_type else None
        results = store.response_cache.get(
            where=where_filter,
            include=["documents", "metadatas"],
            limit=limit
        )
        
        if not results or not results.get("ids"):
            print("📭 No cached items found.")
            return
        
        # Group by cache type
        by_type = {}
        for i, cache_id in enumerate(results["ids"]):
            doc = results["documents"][i] if results.get("documents") else "{}"
            metadata = results["metadatas"][i] if results.get("metadatas") else {}
            ct = metadata.get("cache_type", "unknown")
            if ct not in by_type:
                by_type[ct] = []
            by_type[ct].append((cache_id, metadata, doc))
        
        # Display by type
        for ct, items in by_type.items():
            print(f"\n{'=' * 70}")
            print(f"📁 {ct.upper()} ({len(items)} items)")
            print("=" * 70)
            
            for i, (cache_id, metadata, doc) in enumerate(items[:10]):
                try:
                    data = json.loads(doc)
                    
                    if ct == "job_result":
                        print(f"\n{i+1}. {data.get('title', '?')} @ {data.get('company', '?')}")
                        print(f"   📍 {data.get('location', 'N/A')} | {data.get('platform', '?')}")
                        print(f"   💰 {data.get('salary', 'Not specified')}")
                        print(f"   🔗 {data.get('url', 'No URL')}")
                        
                    elif ct == "job_analysis":
                        print(f"\n{i+1}. Analysis: {data.get('job_title', '?')} @ {data.get('company', '?')}")
                        print(f"   Score: {data.get('match_score', '?')}/100")
                        print(f"   Recommendation: {data.get('recommendation', '?')}")
                        
                    elif ct == "company_analysis":
                        print(f"\n{i+1}. Company: {data.get('company', '?')}")
                        print(f"   Rating: {data.get('rating', '?')}/5")
                        print(f"   Recommend: {data.get('recommend', '?')}")
                        
                    else:
                        print(f"\n{i+1}. {metadata.get('query', cache_id)[:60]}...")
                    
                    print(f"   ⏱️  Cached: {metadata.get('timestamp', '?')[:19]}")
                    
                except Exception as e:
                    print(f"\n{i+1}. Error parsing: {e}")
            
            if len(items) > 10:
                print(f"\n   ... and {len(items) - 10} more")
                
    except Exception as e:
        print(f"❌ Error: {e}")


def clear_cache(cache_type: str = None):
    """Clear cache entries."""
    store = get_vector_store()
    count = store.invalidate_cache(cache_type=cache_type)
    print(f"🗑️  Cleared {count} cache entries")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="View job agent cache")
    parser.add_argument("--type", "-t", help="Filter by cache type (job_result, job_analysis, company_analysis)")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Max items to show")
    parser.add_argument("--clear", "-c", action="store_true", help="Clear the cache")
    args = parser.parse_args()
    
    if args.clear:
        clear_cache(args.type)
    else:
        show_cache(args.type, args.limit)
