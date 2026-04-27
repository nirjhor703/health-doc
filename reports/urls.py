from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_report_view, name='upload_report'),
    path('processing/<int:session_id>/', views.processing_report_view, name='processing_report'),
    path('session/<int:session_id>/attach/', views.attach_report_view, name='attach_report'),
]