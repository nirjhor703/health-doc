from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages

from reports.models import ReportSession
from .models import ChatMessage
from ai_engine.llm import generate_chat_answer_with_gemini
from ai_engine.rag import retrieve_relevant_context


def get_session_report_context(session):
    """
    Fallback: Combine extracted text from all completed uploaded files.
    Used only if RAG retrieval fails or no vector index exists.
    """

    context = ""

    for uploaded_file in session.files.all():
        if uploaded_file.extracted_text and uploaded_file.processing_status == "completed":
            context += f"\n\nFile: {uploaded_file.original_name}\n"
            context += uploaded_file.extracted_text

    return context.strip()


def get_recent_chat_history(session, limit=8):
    """
    Get recent chat messages for conversation memory.
    """

    recent_messages = session.messages.all().order_by("-created_at")[:limit]
    recent_messages = reversed(recent_messages)

    history = []

    for msg in recent_messages:
        history.append({
            "role": msg.role,
            "content": msg.content,
        })

    return history


def build_sources_from_context(context):
    """
    Temporary source builder.
    Since current retrieve_relevant_context returns text only,
    we create a simple source preview from the retrieved context.
    Later we can upgrade rag.py to return exact chunks.
    """

    if not context:
        return []

    sources = []

    sections = context.split("Relevant Section")

    for index, section in enumerate(sections, start=1):
        section = section.strip()

        if not section:
            continue

        preview = section[:500]

        sources.append({
            "title": f"Relevant Section {index}",
            "content": preview,
        })

    if not sources and context:
        sources.append({
            "title": "Uploaded Report Context",
            "content": context[:500],
        })

    return sources[:4]


def chat_room_view(request, session_id):
    session = get_object_or_404(ReportSession, id=session_id)

    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()

        if not user_message:
            messages.error(request, "Please write a message.")
            return redirect("chat_room", session_id=session.id)

        # 1. Save user message
        ChatMessage.objects.create(
            session=session,
            role="user",
            content=user_message,
        )

        # 2. Retrieve relevant report context using RAG
        report_context = retrieve_relevant_context(session, user_message, k=4)

        # 3. Build source previews for UI/debug
        sources = build_sources_from_context(report_context)

        if not report_context:
            if session.language == "bn":
                ai_answer = (
                    "আমি uploaded report/document থেকে কোনো readable text পাইনি। "
                    "অনুগ্রহ করে পরিষ্কার PDF বা image upload করুন।"
                )
            else:
                ai_answer = (
                    "I could not find readable text from the uploaded report/document. "
                    "Please upload a clear PDF or image."
                )

            sources = []

        else:
            chat_history = get_recent_chat_history(session)

            ai_answer = generate_chat_answer_with_gemini(
                report_context=report_context,
                user_question=user_message,
                language=session.language,
                chat_history=chat_history,
            )

        # 4. Save assistant answer with sources
        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=ai_answer,
            sources=sources,
        )

        return redirect("chat_room", session_id=session.id)

    messages_qs = session.messages.all()
    suggested_questions = session.suggested_questions.all()

    return render(request, "reports/chat_room.html", {
        "session": session,
        "messages": messages_qs,
        "suggested_questions": suggested_questions,
    })