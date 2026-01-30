"""
Unit tests for PDF generation and page count validation.

Tests PDF creation and single-page validation without requiring LLM calls.
"""

import pytest
import tempfile
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet


# Test helper to create PDFs
def create_test_pdf(path: str, num_pages: int = 1) -> str:
    """Create a test PDF with specified number of pages."""
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    for i in range(num_pages):
        if i > 0:
            story.append(PageBreak())
        story.append(Paragraph(f"Page {i + 1} content", styles['Normal']))
        story.append(Spacer(1, 100))
    
    doc.build(story)
    return path


class TestPdfPageCount:
    """Tests for PDF page count validation."""
    
    def test_single_page_pdf_detected(self):
        """Test that single page PDF is correctly detected."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=1)
            
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            assert page_count == 1
    
    def test_multi_page_pdf_detected(self):
        """Test that multi-page PDF is correctly detected."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=3)
            
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            assert page_count == 3


class TestValidateSinglePage:
    """Tests for validate_single_page function."""
    
    def test_validate_single_page_returns_true(self):
        """Test that single page PDF passes validation."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import validate_single_page
        except ImportError:
            pytest.skip("PyMuPDF not installed or import error")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=1)
            
            is_single, page_count, msg = validate_single_page(pdf_path)
            
            assert is_single is True
            assert page_count == 1
            assert "single page" in msg.lower()
    
    def test_validate_multi_page_returns_false(self):
        """Test that multi-page PDF fails validation."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import validate_single_page
        except ImportError:
            pytest.skip("PyMuPDF not installed or import error")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=2)
            
            is_single, page_count, msg = validate_single_page(pdf_path)
            
            assert is_single is False
            assert page_count == 2
            assert "2 pages" in msg


class TestGetPdfPageCount:
    """Tests for get_pdf_page_count function."""
    
    def test_get_page_count_single(self):
        """Test page count for single page PDF."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import get_pdf_page_count
        except ImportError:
            pytest.skip("PyMuPDF not installed or import error")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=1)
            
            count = get_pdf_page_count(pdf_path)
            
            assert count == 1
    
    def test_get_page_count_multiple(self):
        """Test page count for multi-page PDF."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import get_pdf_page_count
        except ImportError:
            pytest.skip("PyMuPDF not installed or import error")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = create_test_pdf(f.name, num_pages=5)
            
            count = get_pdf_page_count(pdf_path)
            
            assert count == 5
    
    def test_get_page_count_invalid_file(self):
        """Test error handling for nonexistent PDF."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import get_pdf_page_count
        except ImportError:
            pytest.skip("PyMuPDF not installed or import error")
        
        with pytest.raises(FileNotFoundError):
            get_pdf_page_count("/nonexistent/path.pdf")


class TestResumeContentLength:
    """Tests for resume content that should fit on one page."""
    
    def test_compact_resume_fits_single_page(self):
        """Test that compact resume content generates single-page PDF."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import generate_resume_pdf
        except ImportError:
            pytest.skip("PyMuPDF or imports not available")
        
        # Compact resume content that should fit on one page
        content = """[HEADER]
John Doe
john@example.com | 555-1234 | San Francisco, CA

[SUMMARY]
Experienced engineer with 10 years in software development.

[SKILLS]
Python, Java, AWS, Docker, Kubernetes

[EXPERIENCE]
Senior Engineer | Google | 2020-Present
- Built scalable microservices
- Led team of 5 engineers

Engineer | Meta | 2015-2020
- Developed backend systems

[EDUCATION]
MS Computer Science | Stanford | 2015
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_resume_pdf(
                content=content,
                company="Test Company",
                profile_name="John Doe",
                output_dir=Path(tmpdir)
            )
            
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            assert page_count == 1, f"Resume should be 1 page, got {page_count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
