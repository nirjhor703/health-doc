from django.db import models
from django.contrib.auth.models import User


class ReportSession(models.Model):
    LANGUAGE_CHOICES = [
        ("bn", "Bangla"),
        ("en", "English"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=255, default="Health Report Chat")
    initial_summary = models.TextField(blank=True, null=True)
    vector_index_path = models.CharField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.language} - {self.created_at.strftime('%Y-%m-%d')}"


class UploadedReportFile(models.Model):
    FILE_TYPES = [
        ("pdf", "PDF"),
        ("image", "Image"),
        ("unknown", "Unknown"),
    ]

    PROCESSING_STATUS = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    session = models.ForeignKey(
        ReportSession,
        on_delete=models.CASCADE,
        related_name="files"
    )
    file = models.FileField(upload_to="reports/")
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default="unknown")
    original_name = models.CharField(max_length=255)
    extracted_text = models.TextField(blank=True, null=True)
    processing_status = models.CharField(
        max_length=50,
        choices=PROCESSING_STATUS,
        default="pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_name