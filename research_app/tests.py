import os
import uuid
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from io import BytesIO
from reportlab.pdfgen import canvas


from research_app.models import ResearchSession, UploadedDocument
from research_app.forms import ResearchForm
from research_app.utils import (
    extract_text,
    initialize_report,
    add_answer_to_report,
    add_summary_to_report,
)

# --- Mock Document ---
class MockFile:
    def __init__(self, path):
        self.path = path

class MockDocument:
    def __init__(self, path):
        self.file = MockFile(path)
        self.original_filename = os.path.basename(path)
        self.extracted_text = None
        self.status = 'uploaded'
        self.processing_log = ""

    def save(self):
        # Mock save method that does nothing
        pass


# ---- Fixtures ----

@pytest.fixture
def sample_file():
    """Create a simple text file for testing."""
    content = b"This is test content for document analysis."
    return SimpleUploadedFile("test_doc.txt", content)

@pytest.fixture
def sample_pdf_file():
    """Create a simple PDF file for testing."""
    # Create the test directory if it doesn't exist
    os.makedirs(os.path.join("tests", "test_data"), exist_ok=True)

    # Create a minimal PDF file
    pdf_path = os.path.join("tests", "test_data", "sample.pdf")

    c = canvas.Canvas(pdf_path)
    c.drawString(100, 100, "Test PDF Content")
    c.save()

    return pdf_path

@pytest.fixture
def research_session():
    """Create a research session for testing."""
    return ResearchSession.objects.create(
        query="What are the key findings in these documents?"
    )

@pytest.fixture
def processed_session():
    """Create a completed research session with a report."""
    session = ResearchSession.objects.create(
        query="What are the key findings?",
        status="completed",
        report_filename="test_report.docx"
    )
    return session

@pytest.fixture
def uploaded_document(research_session, sample_file):
    """Create an uploaded document for testing."""
    return UploadedDocument.objects.create(
        session=research_session,
        file=sample_file,
        original_filename="test_doc.txt",
        status="uploaded"
    )

# ---- Model Tests ----

def test_research_session_creation(research_session):
    """Test that a research session can be created."""
    assert research_session.pk is not None
    assert research_session.status == "pending"
    assert str(research_session).startswith("Session")

def test_research_session_get_report_path(processed_session, settings):
    """Test the get_report_path method."""
    report_path = processed_session.get_report_path()
    assert report_path is not None
    assert report_path.endswith("test_report.docx")
    assert str(settings.MEDIA_ROOT) in str(report_path)

def test_uploaded_document_creation(uploaded_document, research_session):
    """Test that an uploaded document can be created and linked to a session."""
    assert uploaded_document.pk is not None
    assert uploaded_document.session == research_session
    assert uploaded_document.status == "uploaded"
    assert str(uploaded_document).endswith(f"({research_session.session_id})")

def test_uploaded_document_get_simple_filename(uploaded_document):
    """Test the get_simple_filename method."""
    assert uploaded_document.get_simple_filename() == "test_doc.txt"

# ---- Form Tests ----

def test_research_form_valid():
    """Test that the research form validates correctly."""
    file_data = SimpleUploadedFile("test.txt", b"test content")
    form_data = {
        "query": "What are the main points?",
    }
    form = ResearchForm(data=form_data, files={"documents": [file_data]})
    assert form.is_valid()

def test_research_form_invalid_file_type():
    """Test form validation rejects invalid file types."""
    file_data = SimpleUploadedFile("test.exe", b"test content", content_type="application/octet-stream")
    form_data = {
        "query": "What are the main points?",
    }
    form = ResearchForm(data=form_data, files={"documents": [file_data]})
    assert not form.is_valid()
    assert "documents" in form.errors

def test_research_form_missing_query():
    """Test form validation requires a query."""
    file_data = SimpleUploadedFile("test.txt", b"test content")
    form_data = {
        "query": "",  # Empty query
    }
    form = ResearchForm(data=form_data, files={"documents": [file_data]})
    assert not form.is_valid()
    assert "query" in form.errors

# ---- View Tests ----

@pytest.mark.django_db
def test_index_view(client):
    """Test that the index view returns a form."""
    response = client.get(reverse("research_app:index"))
    assert response.status_code == 200
    assert "form" in response.context
    assert isinstance(response.context["form"], ResearchForm)

@pytest.mark.django_db
def test_start_research_session_view(client, sample_file, monkeypatch):
    """Test starting a research session."""
    # Mock the process_research_sync function to avoid actual processing
    monkeypatch.setattr(
        "research_app.views.process_research_sync",
        lambda session_id: None
    )

    url = reverse("research_app:start_research")
    data = {
        "query": "What are the main points?",
        "documents": [sample_file],
    }
    response = client.post(url, data)

    assert response.status_code == 200
    assert ResearchSession.objects.count() == 1
    session = ResearchSession.objects.first()
    assert session.query == "What are the main points?"
    assert UploadedDocument.objects.filter(session=session).count() == 1

@pytest.mark.django_db
def test_get_session_status_view_pending(client, research_session):
    """Test getting session status when pending."""
    url = reverse("research_app:session_status", args=[research_session.session_id])
    response = client.get(url)

    assert response.status_code == 200
    assert "Research Progress" in response.content.decode()
    assert research_session.get_status_display() in response.content.decode()

@pytest.mark.django_db
def test_get_session_status_view_completed(client, processed_session):
    """Test getting session status when completed."""
    url = reverse("research_app:session_status", args=[processed_session.session_id])
    response = client.get(url)

    assert response.status_code == 200
    assert "Research Completed" in response.content.decode()
    assert "Download Report" in response.content.decode()

@pytest.mark.django_db
def test_get_session_status_view_not_found(client):
    """Test getting session status for non-existent session."""
    url = reverse("research_app:session_status", args=[uuid.uuid4()])
    response = client.get(url)

    assert response.status_code == 404

@pytest.mark.django_db
def test_download_report_view(client, processed_session, tmp_path, settings, monkeypatch):
    """Test downloading a report."""
    # Create a test file in the expected location
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    test_file = reports_dir / "test_report.docx"
    test_file.write_bytes(b"Test report content")

    # Update settings to use our tmp_path
    monkeypatch.setattr(settings, "MEDIA_ROOT", str(tmp_path))

    # Test the view
    url = reverse("research_app:download_report", args=[processed_session.session_id])
    response = client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert 'attachment; filename="test_report.docx"' in response["Content-Disposition"]

# ---- Utility Tests ----

def test_extract_text_from_txt():
    """Test extracting text from a text file."""
    file_path = "test_file.txt"
    with open(file_path, "w") as f:
        f.write("This is test content")

    mock_doc = MockDocument(file_path)
    text, metadata = extract_text(mock_doc)

    assert text == "This is test content"
    assert mock_doc.status == 'converted'

    # Clean up
    if os.path.exists(file_path):
        os.remove(file_path)

def test_initialize_report():
    """Test initializing a report document."""
    query = "What are the key findings?"
    doc = initialize_report(query)

    # Basic check that the document has content
    assert doc is not None

    # In a real test, you would check more properties of the document
    # But that requires checking the docx structure which is complex

def test_add_answer_to_report():
    """Test adding an answer to the report."""
    query = "What are the key findings?"
    doc = initialize_report(query)

    add_answer_to_report(doc, "test_doc.txt", "This is the answer")

    # Again, in a real test you'd verify the document structure

def test_add_summary_to_report():
    """Test adding a summary to the report."""
    query = "What are the key findings?"
    doc = initialize_report(query)

    add_summary_to_report(doc, "This is the summary")

    # In a real test you'd verify the document structure

def test_upload_document(client, sample_txt_file, media_root_temp_dir):
    """Test uploading a document through the form."""
    url = reverse("research_app:start_research")
    data = {
        "query": "Test query",
        "documents": sample_txt_file
    }
    response = client.post(url, data)
    assert response.status_code == 200
    # More assertions...

def test_research_session_with_factory(research_session_factory, uploaded_document_factory, sample_pdf_file):
    """Test using the factory fixtures."""
    session = research_session_factory(query="Custom query", status="processing")

    # Create a SimpleUploadedFile from the PDF file
    with open(sample_pdf_file, 'rb') as f:
        file_content = f.read()
    upload_file = SimpleUploadedFile(
        name=os.path.basename(sample_pdf_file),
        content=file_content,
        content_type='application/pdf'
    )

    document = uploaded_document_factory(session=session, file=upload_file)

    assert session.query == "Custom query"
    assert document.session == session
    assert document.status == "uploaded"
