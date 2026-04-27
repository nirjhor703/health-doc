from django.urls import path
from . import views

urlpatterns = [
    path('session/<int:session_id>/', views.chat_room_view, name='chat_room'),
]