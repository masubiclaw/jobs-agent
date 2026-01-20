"""TOON format serializer/deserializer for structured data storage."""

import re
from typing import Any, Dict, List, Union
from datetime import datetime


def to_toon(data: Union[Dict, List], indent: int = 0) -> str:
    """
    Convert Python data structure to TOON format.
    
    TOON format rules:
    - Sections marked with [section_name]
    - Key-value pairs as: key: value
    - Lists as numbered items or dash items
    - Nested objects become subsections
    
    Args:
        data: Dictionary or list to convert
        indent: Current indentation level
        
    Returns:
        TOON formatted string
    """
    lines = []
    prefix = "  " * indent
    
    if isinstance(data, dict):
        for key, value in data.items():
            if value is None:
                lines.append(f"{prefix}{key}: null")
            elif isinstance(value, bool):
                lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{prefix}{key}: {value}")
            elif isinstance(value, str):
                # Escape newlines in strings
                escaped = value.replace('\n', '\\n').replace('\r', '\\r')
                lines.append(f"{prefix}{key}: {escaped}")
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{prefix}{key}: []")
                elif all(isinstance(v, (str, int, float, bool)) for v in value):
                    # Simple list - inline
                    items = [str(v) if not isinstance(v, str) else v for v in value]
                    lines.append(f"{prefix}{key}: [{', '.join(items)}]")
                else:
                    # Complex list - expand
                    lines.append(f"{prefix}[{key}]")
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            lines.append(f"{prefix}  [{i}]")
                            lines.append(to_toon(item, indent + 2))
                        else:
                            lines.append(f"{prefix}  - {item}")
            elif isinstance(value, dict):
                if not value:
                    lines.append(f"{prefix}{key}: {{}}")
                else:
                    lines.append(f"{prefix}[{key}]")
                    lines.append(to_toon(value, indent + 1))
            else:
                # Fallback: convert to string
                lines.append(f"{prefix}{key}: {str(value)}")
    
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                lines.append(f"{prefix}[{i}]")
                lines.append(to_toon(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
    
    return '\n'.join(lines)


def from_toon(text: str) -> Dict[str, Any]:
    """
    Parse TOON format back to Python data structure.
    
    Args:
        text: TOON formatted string
        
    Returns:
        Parsed dictionary
    """
    if not text or not text.strip():
        return {}
    
    result = {}
    current_section = None
    current_list = None
    current_list_key = None
    section_stack = [result]
    
    lines = text.strip().split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            i += 1
            continue
        
        # Section header: [section_name] or [0], [1], etc.
        section_match = re.match(r'^\[(\w+|\d+)\]$', stripped)
        if section_match:
            section_name = section_match.group(1)
            
            # Check if numeric (list index)
            if section_name.isdigit():
                idx = int(section_name)
                if current_list is not None:
                    new_dict = {}
                    while len(current_list) <= idx:
                        current_list.append({})
                    current_list[idx] = new_dict
                    section_stack = [result, new_dict]
            else:
                # Named section - create nested dict or list
                parent = section_stack[0] if len(section_stack) == 1 else section_stack[-1]
                if section_name not in parent:
                    parent[section_name] = {}
                section_stack = [result, parent[section_name]]
                current_section = section_name
            
            i += 1
            continue
        
        # Key-value pair: key: value
        kv_match = re.match(r'^(\w+):\s*(.*)$', stripped)
        if kv_match:
            key, value = kv_match.groups()
            parsed_value = _parse_value(value)
            
            target = section_stack[-1] if len(section_stack) > 0 else result
            if isinstance(target, dict):
                target[key] = parsed_value
            
            i += 1
            continue
        
        # List item: - value
        if stripped.startswith('- '):
            value = stripped[2:]
            target = section_stack[-1] if len(section_stack) > 0 else result
            if isinstance(target, list):
                target.append(_parse_value(value))
            
            i += 1
            continue
        
        i += 1
    
    return result


def _parse_value(value: str) -> Any:
    """Parse a TOON value string to Python type."""
    value = value.strip()
    
    # Null
    if value == 'null':
        return None
    
    # Boolean
    if value == 'true':
        return True
    if value == 'false':
        return False
    
    # Empty dict
    if value == '{}':
        return {}
    
    # Empty list or inline list
    if value == '[]':
        return []
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        # Parse comma-separated values
        items = [_parse_value(v.strip()) for v in inner.split(',')]
        return items
    
    # Number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    
    # String (unescape)
    return value.replace('\\n', '\n').replace('\\r', '\r')


def save_toon(filepath: str, data: Union[Dict, List]) -> None:
    """Save data to a TOON file."""
    with open(filepath, 'w') as f:
        f.write(to_toon(data))
        f.write('\n')


def load_toon(filepath: str) -> Dict[str, Any]:
    """Load data from a TOON file."""
    try:
        with open(filepath, 'r') as f:
            return from_toon(f.read())
    except FileNotFoundError:
        return {}
    except Exception as e:
        # Fallback: try JSON (for migration)
        import json
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return {}


# Convenience functions for job cache data
def jobs_to_toon(jobs: Dict[str, Dict]) -> str:
    """Convert jobs dictionary to TOON format."""
    lines = ["[jobs]", f"count: {len(jobs)}", ""]
    
    for job_id, job in jobs.items():
        lines.append(f"[{job_id}]")
        lines.append(f"  title: {job.get('title', 'Unknown')}")
        lines.append(f"  company: {job.get('company', 'Unknown')}")
        lines.append(f"  location: {job.get('location', '')}")
        lines.append(f"  salary: {job.get('salary', '')}")
        lines.append(f"  url: {job.get('url', '')}")
        lines.append(f"  platform: {job.get('platform', '')}")
        lines.append(f"  posted_date: {job.get('posted_date', '')}")
        lines.append(f"  cached_at: {job.get('cached_at', '')}")
        lines.append(f"  search_term: {job.get('search_term', '')}")
        lines.append(f"  search_location: {job.get('search_location', '')}")
        # Description can be long - truncate for storage
        desc = job.get('description', '')
        if desc:
            desc = desc.replace('\n', ' ').replace('\r', '')[:500]
        lines.append(f"  description: {desc}")
        lines.append("")
    
    return '\n'.join(lines)


def jobs_from_toon(text: str) -> Dict[str, Dict]:
    """Parse jobs from TOON format."""
    jobs = {}
    current_id = None
    current_job = {}
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Job ID section
        id_match = re.match(r'^\[([a-f0-9]+)\]$', line)
        if id_match:
            if current_id and current_job:
                jobs[current_id] = current_job
            current_id = id_match.group(1)
            current_job = {'id': current_id}
            continue
        
        # Skip header sections
        if line.startswith('[') and line.endswith(']'):
            continue
        
        # Key-value
        if ':' in line and current_id:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            if key in ('title', 'company', 'location', 'salary', 'url', 'platform', 
                      'posted_date', 'cached_at', 'search_term', 'search_location', 'description'):
                current_job[key] = value if value else ''
    
    # Don't forget last job
    if current_id and current_job:
        jobs[current_id] = current_job
    
    return jobs


def matches_to_toon(matches: Dict[str, Dict]) -> str:
    """Convert matches dictionary to TOON format."""
    lines = ["[matches]", f"count: {len(matches)}", ""]
    
    for match_key, match in matches.items():
        lines.append(f"[{match_key}]")
        lines.append(f"  job_id: {match.get('job_id', '')}")
        lines.append(f"  profile_hash: {match.get('profile_hash', '')}")
        lines.append(f"  match_score: {match.get('match_score', 0)}")
        lines.append(f"  match_level: {match.get('match_level', '')}")
        lines.append(f"  cached_at: {match.get('cached_at', '')}")
        # TOON report - escape newlines
        report = match.get('toon_report', '').replace('\n', '\\n')
        lines.append(f"  toon_report: {report}")
        lines.append("")
    
    return '\n'.join(lines)


def matches_from_toon(text: str) -> Dict[str, Dict]:
    """Parse matches from TOON format."""
    matches = {}
    current_key = None
    current_match = {}
    
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Match key section (job_id:profile_hash or just job_id)
        key_match = re.match(r'^\[([a-f0-9:]+)\]$', line)
        if key_match:
            if current_key and current_match:
                matches[current_key] = current_match
            current_key = key_match.group(1)
            current_match = {}
            continue
        
        # Skip header sections
        if line.startswith('[') and line.endswith(']'):
            continue
        
        # Key-value
        if ':' in line and current_key:
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()
            
            if key == 'match_score':
                current_match[key] = int(value) if value else 0
            elif key == 'toon_report':
                current_match[key] = value.replace('\\n', '\n')
            elif key in ('job_id', 'profile_hash', 'match_level', 'cached_at'):
                current_match[key] = value
    
    # Don't forget last match
    if current_key and current_match:
        matches[current_key] = current_match
    
    return matches
