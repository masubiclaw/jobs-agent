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


class TestHeightCalculation:
    """Tests for pre-rendering height calculation."""
    
    def test_height_calculation_returns_positive(self):
        """Test that height calculation returns a positive value."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import (
                _calculate_story_height, _create_styles, AVAILABLE_WIDTH, AVAILABLE_HEIGHT
            )
        except ImportError:
            pytest.skip("Imports not available")
        
        styles = _create_styles()
        story = [
            Paragraph("Test Header", styles["Name"]),
            Spacer(1, 10),
            Paragraph("Test content paragraph with some text.", styles["Summary"]),
        ]
        
        height = _calculate_story_height(story)
        
        assert height > 0, "Height should be positive"
        assert height < AVAILABLE_HEIGHT * 2, "Height should be reasonable"
    
    def test_more_content_increases_height(self):
        """Test that adding more content increases calculated height."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import (
                _calculate_story_height, _create_styles
            )
        except ImportError:
            pytest.skip("Imports not available")
        
        styles = _create_styles()
        
        # Small story
        small_story = [
            Paragraph("Test content", styles["Summary"]),
        ]
        
        # Large story (more content)
        large_story = [
            Paragraph("Test content", styles["Summary"]),
            Paragraph("More content paragraph one.", styles["Summary"]),
            Paragraph("More content paragraph two.", styles["Summary"]),
            Paragraph("More content paragraph three.", styles["Summary"]),
        ]
        
        small_height = _calculate_story_height(small_story)
        large_height = _calculate_story_height(large_story)
        
        assert large_height > small_height, "More content should increase height"


class TestStyleAdjustments:
    """Tests for style adjustment levels."""
    
    def test_smaller_styles_reduce_height(self):
        """Test that smaller style levels produce shorter content."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import (
                _calculate_story_height, _create_styles, STYLE_ADJUSTMENTS
            )
        except ImportError:
            pytest.skip("Imports not available")
        
        # Sample content
        content = [
            "Test Header Name",
            "This is a summary paragraph with some content.",
            "Bullet point one for experience",
            "Bullet point two for experience",
        ]
        
        heights = []
        for level, adjustment in enumerate(STYLE_ADJUSTMENTS):
            styles = _create_styles(adjustment)
            story = [
                Paragraph(content[0], styles["Name"]),
                Paragraph(content[1], styles["Summary"]),
                Paragraph(f"•  {content[2]}", styles["BulletPoint"]),
                Paragraph(f"•  {content[3]}", styles["BulletPoint"]),
            ]
            height = _calculate_story_height(story)
            heights.append(height)
        
        # Each level should be smaller or equal to the previous
        for i in range(1, len(heights)):
            assert heights[i] <= heights[i-1], f"Level {i} should be <= level {i-1}"
    
    def test_style_adjustment_levels_exist(self):
        """Test that multiple style adjustment levels are defined."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import STYLE_ADJUSTMENTS
        except ImportError:
            pytest.skip("Imports not available")
        
        assert len(STYLE_ADJUSTMENTS) >= 3, "Should have at least 3 style levels"
        
        # Check each level has required keys
        required_keys = ["name_size", "bullet_size", "leading_mult", "spacing_mult"]
        for level, adjustment in enumerate(STYLE_ADJUSTMENTS):
            for key in required_keys:
                assert key in adjustment, f"Level {level} missing key: {key}"


class TestContentFitting:
    """Tests for content fitting functionality."""
    
    def test_content_fits_page_function(self):
        """Test the _content_fits_page helper function."""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import (
                _content_fits_page, _create_styles
            )
        except ImportError:
            pytest.skip("Imports not available")
        
        styles = _create_styles()
        
        # Small story should fit
        small_story = [
            Paragraph("Header", styles["Name"]),
            Paragraph("Content", styles["Summary"]),
        ]
        
        fits, total, available = _content_fits_page(small_story)
        
        assert fits is True, "Small content should fit"
        assert total > 0, "Total height should be positive"
        assert available > 0, "Available height should be positive"
        assert total < available, "Total should be less than available for fitting content"
    
    def test_dense_resume_still_fits_one_page(self):
        """Test that a dense resume with style adjustment still fits one page."""
        try:
            import fitz
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from job_agent_coordinator.tools.pdf_generator import generate_resume_pdf
        except ImportError:
            pytest.skip("PyMuPDF or imports not available")
        
        # Dense resume content with many bullet points
        content = """[HEADER]
Jane Smith
jane@example.com | 555-9876 | New York, NY

[SUMMARY]
Senior software engineer with 15 years of experience building scalable systems.
Expert in cloud architecture, distributed systems, and team leadership.

[SKILLS]
Python, Java, Go, Rust, TypeScript, AWS, GCP, Azure, Kubernetes, Docker, Terraform, PostgreSQL, MongoDB, Redis, Kafka, gRPC

[EXPERIENCE]
Staff Engineer | Amazon | 2020-Present
- Led architecture redesign reducing latency by 40%
- Built ML pipeline processing 10M events daily
- Mentored team of 8 junior engineers
- Implemented CI/CD reducing deployment time by 60%

Senior Engineer | Microsoft | 2015-2020
- Developed core authentication service for Azure
- Optimized database queries improving performance 3x
- Led migration from monolith to microservices
- Built real-time analytics dashboard

Software Engineer | Startup Inc | 2010-2015
- Built MVP from scratch, grew to 100K users
- Implemented payment processing system
- Created mobile app backend

[EDUCATION]
MS Computer Science | MIT | 2010
BS Computer Science | Berkeley | 2008
"""
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = generate_resume_pdf(
                content=content,
                company="Dense Resume Test",
                profile_name="Jane Smith",
                output_dir=Path(tmpdir)
            )
            
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            
            assert page_count == 1, f"Dense resume should still be 1 page (with style adjustment), got {page_count}"


class TestDocumentServicePdfPathValidation:
    """Tests for PDF path validation in DocumentService.get_document_pdf()."""

    def test_generated_documents_dir_is_allowed(self):
        """PDF paths in generated_documents/ should be allowed by path validation."""
        import sys
        import json
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from api.services.document_service import DocumentService

        svc = DocumentService()

        # Create a test PDF in generated_documents/
        gen_dir = Path("generated_documents")
        gen_dir.mkdir(exist_ok=True)
        test_pdf = gen_dir / "_test_path_validation.pdf"
        create_test_pdf(str(test_pdf), num_pages=1)

        try:
            # Create a fake user docs index with the PDF path
            test_user = "_test_path_validation_user"
            svc._save_docs_index(test_user, {
                "test_doc_1": {
                    "id": "test_doc_1",
                    "pdf_path": str(test_pdf),
                    "job_id": "j1",
                    "profile_id": "p1",
                    "document_type": "resume",
                }
            })

            result = svc.get_document_pdf("test_doc_1", test_user)
            assert result is not None, (
                "get_document_pdf returned None for a valid PDF in generated_documents/. "
                "The generated_documents/ dir must be in allowed_dirs."
            )
            assert result.exists()
            assert result.suffix == ".pdf"
        finally:
            test_pdf.unlink(missing_ok=True)
            # Clean up test index
            index_file = svc._docs_index_file(test_user)
            index_file.unlink(missing_ok=True)
            index_file.parent.rmdir()
            index_file.parent.parent.rmdir()

    def test_disallowed_dir_is_blocked(self):
        """PDF paths outside allowed dirs should be blocked."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from api.services.document_service import DocumentService

        svc = DocumentService()

        # Create a test PDF in a non-allowed directory
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, dir='.') as f:
            test_pdf = Path(f.name)
            create_test_pdf(str(test_pdf), num_pages=1)

        try:
            test_user = "_test_blocked_path_user"
            svc._save_docs_index(test_user, {
                "test_doc_2": {
                    "id": "test_doc_2",
                    "pdf_path": "/etc/passwd",
                    "job_id": "j1",
                    "profile_id": "p1",
                    "document_type": "resume",
                }
            })

            result = svc.get_document_pdf("test_doc_2", test_user)
            assert result is None, "Path traversal to /etc/passwd should be blocked"
        finally:
            test_pdf.unlink(missing_ok=True)
            index_file = svc._docs_index_file(test_user)
            index_file.unlink(missing_ok=True)
            index_file.parent.rmdir()
            index_file.parent.parent.rmdir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
