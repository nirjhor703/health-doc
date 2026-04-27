from django.contrib import admin
from .models import ChatMessage, SuggestedQuestion


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content",)


@admin.register(SuggestedQuestion)
class SuggestedQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "question", "language", "created_at")
    list_filter = ("language", "created_at")
    search_fields = ("question",)