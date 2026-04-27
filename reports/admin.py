from django.contrib import admin
from .models import ReportSession, UploadedReportFile


class UploadedReportFileInline(admin.TabularInline):
    model = UploadedReportFile
    extra = 0


@admin.register(ReportSession)
class ReportSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "language", "status", "created_at")
    list_filter = ("language", "status", "created_at")
    search_fields = ("title",)
    inlines = [UploadedReportFileInline]


@admin.register(UploadedReportFile)
class UploadedReportFileAdmin(admin.ModelAdmin):
    list_display = ("id", "original_name", "file_type", "processing_status", "created_at")
    list_filter = ("file_type", "processing_status", "created_at")
    search_fields = ("original_name",)