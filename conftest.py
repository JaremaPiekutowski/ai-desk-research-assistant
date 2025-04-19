import pytest
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings

# This is needed to use the database
pytest_plugins = ["pytest_django"]

# Mark all tests that use the database
@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Give all tests access to the database.
    If specific tests don't need the database,
    you can remove this and use @pytest.mark.django_db directly.
    """
    pass

@pytest.fixture
def client_user():
    """A logged-in user client."""
    from django.contrib.auth.models import User
    from django.test import Client
    client = Client()
    user = User.objects.create_user(username='testuser', password='testpass')
    client.login(username='testuser', password='testpass')
    return client, user

@pytest.fixture
def admin_client():
    """A logged-in admin client."""
    from django.contrib.auth.models import User
    from django.test import Client
    client = Client()
    admin = User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')
    client.login(username='admin', password='adminpass')
    return client

@pytest.fixture
def sample_txt_file():
    """Create a simple text file for testing."""
    content = b"This is test content for document analysis."
    return SimpleUploadedFile("test_doc.txt", content)

@pytest.fixture
def sample_pdf_file():
    """Create a simple PDF file for testing.

    Note: This assumes you have a test.pdf file in a test_data directory.
    If not, you'll need to create or mock this.
    """
    test_file_path = os.path.join(settings.BASE_DIR, 'tests', 'test_data', 'test.pdf')
    try:
        with open(test_file_path, "rb") as f:
            content = f.read()
        return SimpleUploadedFile("test.pdf", content, content_type="application/pdf")
    except FileNotFoundError:
        # Fallback if the file doesn't exist - create a mock PDF
        # This is just a placeholder, not a real PDF
        return SimpleUploadedFile("test.pdf", b"%PDF-1.4 mock pdf content", content_type="application/pdf")

@pytest.fixture
def sample_docx_file():
    """Create a mock DOCX file for testing."""
    # This is just a placeholder, not a real DOCX file
    return SimpleUploadedFile(
        "test.docx",
        b"Mock DOCX content",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@pytest.fixture
def media_root_temp_dir(settings, tmp_path):
    """Set MEDIA_ROOT to a temporary directory during tests.

    This helps isolate file operations during tests.
    """
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    settings.MEDIA_ROOT = str(media_dir)
    return settings.MEDIA_ROOT

@pytest.fixture
def research_session_factory():
    """Factory for creating ResearchSession instances."""
    from research_app.models import ResearchSession

    def _create_session(query="Test query", status="pending", **kwargs):
        return ResearchSession.objects.create(
            query=query,
            status=status,
            **kwargs
        )

    return _create_session

@pytest.fixture
def uploaded_document_factory():
    """Factory for creating UploadedDocument instances."""
    from research_app.models import UploadedDocument

    def _create_document(session, file, original_filename=None, status="uploaded", **kwargs):
        if original_filename is None:
            original_filename = file.name

        return UploadedDocument.objects.create(
            session=session,
            file=file,
            original_filename=original_filename,
            status=status,
            **kwargs
        )

    return _create_document
