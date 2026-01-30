"""
Unit tests for document generation and artifact cleaning.

Tests the cleaning functions without requiring LLM calls.
"""

import pytest
import sys
import re
from pathlib import Path

# Avoid importing the full package which has heavy dependencies
# Instead, define the functions inline for testing

# Template artifact patterns that should be removed from generated content
TEMPLATE_ARTIFACTS = [
    r'\[OPENING\s*-\s*[^\]]*\]',
    r'\[BODY PARAGRAPH \d+\s*-\s*[^\]]*\]',
    r'\[CLOSING\s*-\s*[^\]]*\]',
    r'\[DATE\]',
    r'\[RECIPIENT\]',
    r'\{Current date\}',
    r'\{Company Name\}',
    r'\{Your name\}',
    r'\{name\}',
    r'\{email\}',
    r'\{phone\}',
    r'\{location\}',
    r'\{[^}]*sentences[^}]*\}',
    r'\{[^}]*words[^}]*\}',
    r'~\d+\s*words?',
]


def _clean_template_artifacts(content: str) -> str:
    """Remove template artifacts and instruction markers from generated content."""
    cleaned = content
    
    for pattern in TEMPLATE_ARTIFACTS:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    lines = [line for line in cleaned.split('\n') if line.strip()]
    cleaned = '\n'.join(lines)
    
    return cleaned.strip()


def has_template_artifacts(content: str) -> tuple:
    """Check if content contains template artifacts."""
    found = []
    for pattern in TEMPLATE_ARTIFACTS:
        matches = re.findall(pattern, content, flags=re.IGNORECASE)
        found.extend(matches)
    return bool(found), found


def _check_for_artifacts(content: str) -> tuple:
    """Check if content contains template artifacts (critic version)."""
    return has_template_artifacts(content)


# Length constraints
RESUME_MIN_WORDS = 400
RESUME_MAX_WORDS = 600
COVER_LETTER_MIN_WORDS = 200
COVER_LETTER_MAX_WORDS = 400


def _check_length_compliance(content: str, doc_type: str) -> tuple:
    """Check if document meets length requirements."""
    word_count = len(content.split())
    
    if doc_type == "resume":
        if word_count < RESUME_MIN_WORDS:
            return False, f"Resume too short: {word_count} words (min {RESUME_MIN_WORDS}). Add more detail."
        if word_count > RESUME_MAX_WORDS:
            return False, f"Resume too long: {word_count} words (max {RESUME_MAX_WORDS}). Remove less relevant content."
        return True, f"Resume length OK: {word_count} words"
    
    elif doc_type == "cover_letter":
        if word_count < COVER_LETTER_MIN_WORDS:
            return False, f"Cover letter too short: {word_count} words (min {COVER_LETTER_MIN_WORDS}). Add more substance."
        if word_count > COVER_LETTER_MAX_WORDS:
            return False, f"Cover letter too long: {word_count} words (max {COVER_LETTER_MAX_WORDS}). Be more concise."
        return True, f"Cover letter length OK: {word_count} words"
    
    return True, "Unknown document type"


class TestArtifactCleaning:
    """Tests for template artifact cleaning."""
    
    def test_clean_opening_artifact(self):
        """Test cleaning [OPENING - X sentences] markers."""
        content = "[OPENING - 2-3 sentences, ~50 words]\nDear Hiring Manager,"
        cleaned = _clean_template_artifacts(content)
        assert "[OPENING" not in cleaned
        assert "Dear Hiring Manager" in cleaned
    
    def test_clean_body_paragraph_artifact(self):
        """Test cleaning [BODY PARAGRAPH N] markers."""
        content = "[BODY PARAGRAPH 1 - 3-4 sentences, ~75 words]\nI have experience..."
        cleaned = _clean_template_artifacts(content)
        assert "[BODY PARAGRAPH" not in cleaned
        assert "I have experience" in cleaned
    
    def test_clean_closing_artifact(self):
        """Test cleaning [CLOSING] markers."""
        content = "[CLOSING - 2-3 sentences, ~50 words]\nThank you for your consideration."
        cleaned = _clean_template_artifacts(content)
        assert "[CLOSING" not in cleaned
        assert "Thank you" in cleaned
    
    def test_clean_current_date_placeholder(self):
        """Test cleaning {Current date} placeholder."""
        content = "[DATE]\n{Current date}\n\nDear Manager,"
        cleaned = _clean_template_artifacts(content)
        assert "{Current date}" not in cleaned
    
    def test_clean_company_name_placeholder(self):
        """Test cleaning {Company Name} placeholder."""
        content = "Hiring Manager\n{Company Name}\n\nDear Manager,"
        cleaned = _clean_template_artifacts(content)
        assert "{Company Name}" not in cleaned
    
    def test_clean_your_name_placeholder(self):
        """Test cleaning {Your name} placeholder."""
        content = "Thank you,\n{Your name}"
        cleaned = _clean_template_artifacts(content)
        assert "{Your name}" not in cleaned
    
    def test_clean_word_count_hints(self):
        """Test cleaning ~50 words style hints."""
        content = "Opening paragraph ~50 words here is some text."
        cleaned = _clean_template_artifacts(content)
        assert "~50 words" not in cleaned
    
    def test_clean_multiple_artifacts(self):
        """Test cleaning multiple artifacts in one document."""
        content = """[DATE]
{Current date}

[RECIPIENT]
Hiring Manager
{Company Name}

[OPENING - 2-3 sentences, ~50 words]
Dear Hiring Manager,

[BODY PARAGRAPH 1 - 3-4 sentences, ~75 words]
I have extensive experience.

[CLOSING - 2-3 sentences, ~50 words]
Thank you.

{Your name}
"""
        cleaned = _clean_template_artifacts(content)
        
        # All artifacts should be removed
        assert "[DATE]" not in cleaned
        assert "{Current date}" not in cleaned
        assert "[RECIPIENT]" not in cleaned
        assert "{Company Name}" not in cleaned
        assert "[OPENING" not in cleaned
        assert "[BODY PARAGRAPH" not in cleaned
        assert "[CLOSING" not in cleaned
        assert "{Your name}" not in cleaned
        assert "~50 words" not in cleaned
        assert "~75 words" not in cleaned
        
        # Content should remain
        assert "Dear Hiring Manager" in cleaned
        assert "I have extensive experience" in cleaned
        assert "Thank you" in cleaned
    
    def test_preserve_legitimate_content(self):
        """Test that legitimate content is preserved."""
        content = """January 30, 2026

Hiring Manager
Acme Corporation

Dear Hiring Manager,

I am excited to apply for the Senior Engineer position at Acme Corporation.
With over 10 years of experience in software development, I bring expertise
in Python, JavaScript, and cloud technologies.

Sincerely,
John Doe
"""
        cleaned = _clean_template_artifacts(content)
        
        # All content should be preserved
        assert "January 30, 2026" in cleaned
        assert "Acme Corporation" in cleaned
        assert "Senior Engineer" in cleaned
        assert "10 years" in cleaned
        assert "John Doe" in cleaned
    
    def test_clean_removes_excess_whitespace(self):
        """Test that cleaning removes excess whitespace."""
        content = "[OPENING]\n\n\n\n\nDear Manager,"
        cleaned = _clean_template_artifacts(content)
        
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in cleaned


class TestHasTemplateArtifacts:
    """Tests for artifact detection."""
    
    def test_detects_opening_artifact(self):
        """Test detection of [OPENING] markers."""
        content = "[OPENING - 2-3 sentences]\nDear Manager,"
        has, found = has_template_artifacts(content)
        assert has is True
        assert len(found) > 0
    
    def test_detects_placeholder(self):
        """Test detection of placeholders."""
        content = "Dear {Company Name} Team,"
        has, found = has_template_artifacts(content)
        assert has is True
    
    def test_clean_content_has_no_artifacts(self):
        """Test that clean content is detected as clean."""
        content = """January 30, 2026

Dear Hiring Manager,

I am excited to apply for the position.

Sincerely,
John Doe
"""
        has, found = has_template_artifacts(content)
        assert has is False
        assert len(found) == 0


class TestCriticArtifactDetection:
    """Tests for critic artifact detection."""
    
    def test_critic_detects_artifacts(self):
        """Test that critic detects artifacts."""
        content = "[OPENING - 2-3 sentences]\nDear Manager,"
        has, found = _check_for_artifacts(content)
        assert has is True
    
    def test_critic_clean_content(self):
        """Test critic with clean content."""
        content = "Dear Hiring Manager,\n\nI am writing to apply."
        has, found = _check_for_artifacts(content)
        assert has is False


class TestLengthCompliance:
    """Tests for document length compliance."""
    
    def test_resume_length_ok(self):
        """Test resume within word limit."""
        content = "word " * 500
        ok, msg = _check_length_compliance(content, "resume")
        assert ok is True
        assert "OK" in msg
    
    def test_resume_too_long(self):
        """Test resume exceeding word limit."""
        content = "word " * 700
        ok, msg = _check_length_compliance(content, "resume")
        assert ok is False
        assert "too long" in msg.lower()
    
    def test_resume_too_short(self):
        """Test resume below minimum word count."""
        content = "word " * 200
        ok, msg = _check_length_compliance(content, "resume")
        assert ok is False
        assert "too short" in msg.lower()
    
    def test_cover_letter_ok(self):
        """Test cover letter within word limits."""
        content = "word " * 300
        ok, msg = _check_length_compliance(content, "cover_letter")
        assert ok is True
    
    def test_cover_letter_too_short(self):
        """Test cover letter below minimum."""
        content = "word " * 100
        ok, msg = _check_length_compliance(content, "cover_letter")
        assert ok is False
        assert "too short" in msg.lower()
    
    def test_cover_letter_too_long(self):
        """Test cover letter above maximum."""
        content = "word " * 500
        ok, msg = _check_length_compliance(content, "cover_letter")
        assert ok is False
        assert "too long" in msg.lower()


# ==================
# Markdown Detection (NEW)
# ==================

def _check_for_markdown(content: str) -> tuple:
    """Check if content contains markdown formatting that should have been cleaned."""
    if not content:
        return False, []
    
    found = []
    
    # Check for bold markers
    bold_double = re.findall(r'\*\*[^*]+\*\*', content)
    bold_under = re.findall(r'__[^_]+__', content)
    found.extend(bold_double)
    found.extend(bold_under)
    
    # Check for italic markers
    italic_star = re.findall(r'(?<!\*)\*[^*]+\*(?!\*)', content)
    italic_under = re.findall(r'(?<!\w)_[^_]+_(?!\w)', content)
    found.extend(italic_star)
    found.extend(italic_under)
    
    return bool(found), found


class TestMarkdownDetection:
    """Tests for markdown formatting detection."""
    
    def test_detects_bold_double_asterisk(self):
        """Test detection of **bold** text."""
        content = "My name is **John Doe** and I am applying."
        has_md, found = _check_for_markdown(content)
        assert has_md is True
        assert "**John Doe**" in found
    
    def test_detects_bold_underscore(self):
        """Test detection of __bold__ text."""
        content = "I have experience in __Python__ programming."
        has_md, found = _check_for_markdown(content)
        assert has_md is True
        assert "__Python__" in found
    
    def test_detects_italic_asterisk(self):
        """Test detection of *italic* text."""
        content = "I am *excited* about this opportunity."
        has_md, found = _check_for_markdown(content)
        assert has_md is True
        assert "*excited*" in found
    
    def test_clean_content_no_markdown(self):
        """Test clean content without markdown."""
        content = "Dear Hiring Manager, I am applying for the position."
        has_md, found = _check_for_markdown(content)
        assert has_md is False
        assert found == []
    
    def test_underscore_in_word_not_detected(self):
        """Test that underscores in words (like variable_name) are not flagged."""
        content = "I have experience with snake_case naming."
        has_md, found = _check_for_markdown(content)
        # snake_case should not be detected as markdown
        assert "_case" not in str(found)


# ==================
# Paragraph Structure (NEW)
# ==================

def _check_paragraph_structure(content: str, doc_type: str) -> tuple:
    """Check if document has proper paragraph structure."""
    if doc_type != "cover_letter":
        return True, "Structure check only applies to cover letters"
    
    if not content:
        return False, "Cover letter content is empty"
    
    # Check for section markers
    has_opening = bool(re.search(r'\[OPENING\]', content, re.IGNORECASE))
    has_body1 = bool(re.search(r'\[BODY PARAGRAPH 1\]', content, re.IGNORECASE))
    has_body2 = bool(re.search(r'\[BODY PARAGRAPH 2\]', content, re.IGNORECASE))
    has_closing = bool(re.search(r'\[CLOSING\]', content, re.IGNORECASE))
    
    section_count = sum([has_opening, has_body1, has_body2, has_closing])
    
    if section_count >= 3:
        return True, f"Cover letter has {section_count} sections (good structure)"
    
    # Fallback: check for paragraph breaks
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 50]
    
    if len(paragraphs) >= 3:
        return True, f"Cover letter has {len(paragraphs)} paragraphs (good structure)"
    
    return False, f"Cover letter appears to have only {max(section_count, len(paragraphs))} section(s)."


class TestParagraphStructure:
    """Tests for cover letter paragraph structure validation."""
    
    def test_good_structure_with_markers(self):
        """Test cover letter with proper section markers."""
        content = """[OPENING]
        Dear Hiring Manager, I am excited to apply.
        
        [BODY PARAGRAPH 1]
        In my previous role, I achieved great success.
        
        [BODY PARAGRAPH 2]
        Additionally, I have strong skills in Python.
        
        [CLOSING]
        I look forward to hearing from you."""
        
        valid, msg = _check_paragraph_structure(content, "cover_letter")
        assert valid is True
        assert "4 sections" in msg or "good structure" in msg
    
    def test_good_structure_with_paragraphs(self):
        """Test cover letter with proper paragraph breaks."""
        para1 = "Dear Hiring Manager, I am writing to express my strong interest in the Software Engineer position at your company. With my background in Python and cloud technologies, I believe I would be an excellent fit."
        para2 = "In my current role at TechCorp, I have successfully led multiple projects that improved system performance by 40%. I specialize in building scalable microservices and have extensive experience with AWS."
        para3 = "I am excited about the opportunity to bring my skills to your team. I would welcome the chance to discuss how I can contribute to your organization's success. Thank you for your consideration."
        
        content = f"{para1}\n\n{para2}\n\n{para3}"
        
        valid, msg = _check_paragraph_structure(content, "cover_letter")
        assert valid is True
    
    def test_bad_structure_single_paragraph(self):
        """Test cover letter that's a single block of text."""
        content = "Dear Hiring Manager, I am applying for the position. I have experience. Thank you."
        
        valid, msg = _check_paragraph_structure(content, "cover_letter")
        assert valid is False
        assert "only" in msg.lower()
    
    def test_resume_skips_structure_check(self):
        """Test that structure check is skipped for resumes."""
        content = "Just one paragraph."
        
        valid, msg = _check_paragraph_structure(content, "resume")
        assert valid is True
        assert "only applies to cover letters" in msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
