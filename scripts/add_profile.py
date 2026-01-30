#!/usr/bin/env python3
"""
Create a new user profile for job searching.

Supports both interactive mode and command-line arguments.

Usage:
    # Interactive mode
    python scripts/add_profile.py
    
    # Command-line mode
    python scripts/add_profile.py --name "John Doe" --email "john@example.com"
    
    # Full profile
    python scripts/add_profile.py \\
        --name "John Doe" \\
        --email "john@example.com" \\
        --phone "555-1234" \\
        --location "Seattle, WA" \\
        --summary "Experienced software engineer" \\
        --skills "python,java,kubernetes" \\
        --target-roles "Software Engineer,Tech Lead" \\
        --exclude "Amazon,Meta"
"""

import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def interactive_mode():
    """Run interactive profile creation."""
    print("=" * 60)
    print("CREATE NEW PROFILE")
    print("=" * 60)
    print("Enter profile details (press Enter to skip optional fields)")
    print()
    
    # Required field
    name = input("Full name (required): ").strip()
    if not name:
        print("Error: Name is required")
        sys.exit(1)
    
    # Optional fields
    email = input("Email: ").strip()
    phone = input("Phone: ").strip()
    location = input("Location (e.g., Seattle, WA): ").strip()
    
    # Professional summary
    print()
    print("Professional summary (1-2 sentences, press Enter twice to finish):")
    summary_lines = []
    while True:
        line = input()
        if not line:
            break
        summary_lines.append(line)
    summary = " ".join(summary_lines)
    
    # Skills
    print()
    skills_input = input("Skills (comma-separated, e.g., python,java,kubernetes): ").strip()
    skills = [s.strip() for s in skills_input.split(",") if s.strip()] if skills_input else []
    
    # Target roles
    target_roles_input = input("Target roles (comma-separated, e.g., Software Engineer,Tech Lead): ").strip()
    target_roles = [r.strip() for r in target_roles_input.split(",") if r.strip()] if target_roles_input else []
    
    # Excluded companies
    excluded_input = input("Companies to exclude (comma-separated): ").strip()
    excluded = [c.strip() for c in excluded_input.split(",") if c.strip()] if excluded_input else []
    
    # Remote preference
    print()
    print("Remote preference:")
    print("  1. Remote")
    print("  2. Hybrid (default)")
    print("  3. Onsite")
    remote_choice = input("Choice [2]: ").strip()
    remote_map = {"1": "remote", "2": "hybrid", "3": "onsite"}
    remote_preference = remote_map.get(remote_choice, "hybrid")
    
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "summary": summary,
        "skills": skills,
        "target_roles": target_roles,
        "excluded_companies": excluded,
        "remote_preference": remote_preference,
    }


def create_profile(data: dict) -> str:
    """Create profile from data dictionary."""
    from job_agent_coordinator.tools.profile_store import get_store
    
    store = get_store()
    
    # Create base profile
    profile = store.create(
        name=data["name"],
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        location=data.get("location", ""),
    )
    
    profile_id = profile["id"]
    
    # Add skills
    for skill in data.get("skills", []):
        store.add_skill(skill, "intermediate", profile_id)
    
    # Set resume summary
    if data.get("summary"):
        store.set_resume(summary=data["summary"], profile_id=profile_id)
    
    # Set preferences
    store.set_preferences(
        target_roles=data.get("target_roles", []),
        excluded_companies=data.get("excluded_companies", []),
        remote_preference=data.get("remote_preference", "hybrid"),
        profile_id=profile_id,
    )
    
    return profile_id


def main():
    parser = argparse.ArgumentParser(
        description="Create a new user profile for job searching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Interactive mode
    python scripts/add_profile.py
    
    # Basic profile
    python scripts/add_profile.py --name "John Doe" --email "john@example.com"
    
    # Full profile
    python scripts/add_profile.py \\
        --name "John Doe" \\
        --email "john@example.com" \\
        --phone "555-1234" \\
        --location "Seattle, WA" \\
        --summary "10 years of software engineering experience" \\
        --skills "python,java,kubernetes,aws" \\
        --target-roles "Senior Engineer,Tech Lead" \\
        --exclude "Amazon,Meta,Apple"
"""
    )
    
    parser.add_argument("--name", help="Full name (required in CLI mode)")
    parser.add_argument("--email", default="", help="Email address")
    parser.add_argument("--phone", default="", help="Phone number")
    parser.add_argument("--location", default="", help="Location (e.g., Seattle, WA)")
    parser.add_argument("--summary", default="", help="Professional summary")
    parser.add_argument("--skills", default="", help="Skills (comma-separated)")
    parser.add_argument("--target-roles", default="", help="Target job roles (comma-separated)")
    parser.add_argument("--exclude", default="", help="Companies to exclude (comma-separated)")
    parser.add_argument(
        "--remote",
        choices=["remote", "hybrid", "onsite"],
        default="hybrid",
        help="Remote preference (default: hybrid)"
    )
    parser.add_argument("--list", action="store_true", help="List existing profiles")
    
    args = parser.parse_args()
    
    # Handle --list
    if args.list:
        from job_agent_coordinator.tools.profile_store import get_store
        store = get_store()
        profiles = store.list_profiles()
        
        if not profiles:
            print("No profiles found.")
            return
        
        print("=" * 60)
        print("EXISTING PROFILES")
        print("=" * 60)
        for p in profiles:
            active = " (active)" if p.get("id") == store._active_profile else ""
            print(f"  - {p.get('name')} ({p.get('id')}){active}")
        print()
        return
    
    # Determine mode
    if args.name:
        # CLI mode
        data = {
            "name": args.name,
            "email": args.email,
            "phone": args.phone,
            "location": args.location,
            "summary": args.summary,
            "skills": [s.strip() for s in args.skills.split(",") if s.strip()],
            "target_roles": [r.strip() for r in args.target_roles.split(",") if r.strip()],
            "excluded_companies": [c.strip() for c in args.exclude.split(",") if c.strip()],
            "remote_preference": args.remote,
        }
    else:
        # Interactive mode
        data = interactive_mode()
    
    # Create profile
    print()
    print("Creating profile...")
    profile_id = create_profile(data)
    
    print()
    print("=" * 60)
    print("PROFILE CREATED SUCCESSFULLY")
    print("=" * 60)
    print(f"  Name: {data['name']}")
    print(f"  ID: {profile_id}")
    if data.get("email"):
        print(f"  Email: {data['email']}")
    if data.get("location"):
        print(f"  Location: {data['location']}")
    if data.get("skills"):
        print(f"  Skills: {len(data['skills'])} added")
    if data.get("target_roles"):
        print(f"  Target roles: {', '.join(data['target_roles'])}")
    if data.get("excluded_companies"):
        print(f"  Excluded: {', '.join(data['excluded_companies'])}")
    print()
    print("Next steps:")
    print("  1. Run job scraper: python scripts/run_job_scraper.py")
    print("  2. Run job matcher: python scripts/run_job_matcher.py")
    print("  3. View matches: python scripts/show_top_matches.py")


if __name__ == "__main__":
    main()
