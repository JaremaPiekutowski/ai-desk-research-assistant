import uuid
import os

from django.db import models
from django.conf import settings

class ResearchSession(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing Documents'),
        ('summarizing', 'Generating Summary'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    report_filename = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Session {self.session_id} - {self.status}"

    def get_report_path(self):
        if self.report_filename:
            return os.path.join(settings.MEDIA_ROOT, 'reports', self.report_filename)
        return None

def get_upload_path(instance, filename):
    # Files will be uploaded to MEDIA_ROOT/uploads/<session_id>/<filename>
    return f'uploads/{instance.session.session_id}/{filename}'

class UploadedDocument(models.Model):
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('converting', 'Converting'),
        ('converted', 'Converted'),
        ('processing', 'Querying LLM'),
        ('processed', 'Processed'),
        ('error', 'Error'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ResearchSession, related_name='documents', on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_upload_path)
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    extracted_text = models.TextField(blank=True, null=True) # Store extracted text if needed, or extract on the fly
    processing_log = models.TextField(blank=True, null=True) # Store errors or info

    def __str__(self):
        return f"{self.original_filename} ({self.session.session_id})"

    def get_simple_filename(self):
        return os.path.basename(self.original_filename)
