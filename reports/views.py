from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import ReportSession, UploadedReportFile
from .extractors import extract_text_from_pdf, clean_extracted_text

from ai_engine.llm import (
    extract_text_from_image_with_gemini,
    generate_initial_summary_with_gemini,
)
from ai_engine.rag import create_faiss_index_for_session

from chat.models import ChatMessage, SuggestedQuestion


def landing_view(request):
    return render(request, "landing.html")


def get_file_type(uploaded_file):
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return "pdf"

    if name.endswith((".jpg", ".jpeg", ".png", ".webp")):
        return "image"

    return "unknown"


def process_single_uploaded_file(uploaded_file):
    """
    Extract text from a single UploadedReportFile object.
    Updates extracted_text and processing_status.
    Used for both initial upload and attaching more reports.
    """

    uploaded_file.processing_status = "processing"
    uploaded_file.save()

    try:
        if uploaded_file.file_type == "pdf":
            raw_text = extract_text_from_pdf(uploaded_file.file.path)
            cleaned_text = clean_extracted_text(raw_text)

            uploaded_file.extracted_text = cleaned_text
            uploaded_file.processing_status = "completed"
            uploaded_file.save()

        elif uploaded_file.file_type == "image":
            raw_text = extract_text_from_image_with_gemini(uploaded_file.file.path)
            cleaned_text = clean_extracted_text(raw_text)

            uploaded_file.extracted_text = cleaned_text
            uploaded_file.processing_status = "completed"
            uploaded_file.save()

        else:
            uploaded_file.extracted_text = "Unsupported file type."
            uploaded_file.processing_status = "failed"
            uploaded_file.save()

    except Exception as e:
        uploaded_file.extracted_text = f"TEXT_EXTRACTION_ERROR: {str(e)}"
        uploaded_file.processing_status = "failed"
        uploaded_file.save()


def get_all_extracted_text_for_session(session):
    """
    Combine extracted text from all completed files in a session.
    """

    all_extracted_text = ""

    for uploaded_file in session.files.all():
        if uploaded_file.extracted_text and uploaded_file.processing_status == "completed":
            all_extracted_text += f"\n\nFile: {uploaded_file.original_name}\n"
            all_extracted_text += uploaded_file.extracted_text

    return all_extracted_text.strip()


def rebuild_session_vector_index(session):
    """
    Rebuild FAISS index using all completed files in this session.
    """

    vector_path = create_faiss_index_for_session(session)

    if vector_path:
        session.vector_index_path = vector_path
        session.save()

    return vector_path


def create_default_suggested_questions(session):
    """
    Create language-based suggested questions for the chat page.
    """

    if session.language == "bn":
        questions = [
            "এই রিপোর্টের সহজ summary বলো",
            "কোন value গুলো normal range-এর বাইরে?",
            "আমার daily life-এ কী কী খেয়াল রাখা উচিত?",
            "আমার কোন ধরনের doctor দেখানো উচিত?",
            "Doctor কে কী কী প্রশ্ন করা উচিত?",
        ]
    else:
        questions = [
            "Summarize this report in simple language",
            "Which values are outside the normal range?",
            "What lifestyle points should I consider?",
            "What type of doctor should I consult?",
            "What questions should I ask my doctor?",
        ]

    for question in questions:
        SuggestedQuestion.objects.get_or_create(
            session=session,
            question=question,
            language=session.language,
        )


def upload_report_view(request):
    if request.method == "POST":
        language = request.POST.get("language")
        uploaded_files = request.FILES.getlist("files")
        camera_file = request.FILES.get("camera_file")

        if not language:
            messages.error(request, "Please select a language.")
            return redirect("upload_report")

        all_files = []

        if uploaded_files:
            all_files.extend(uploaded_files)

        if camera_file:
            all_files.append(camera_file)

        if not all_files:
            messages.error(request, "Please upload at least one report file.")
            return redirect("upload_report")

        session = ReportSession.objects.create(
            language=language,
            status="pending",
        )

        for file in all_files:
            file_type = get_file_type(file)

            UploadedReportFile.objects.create(
                session=session,
                file=file,
                file_type=file_type,
                original_name=file.name,
                processing_status="pending",
            )

        return redirect("processing_report", session_id=session.id)

    return render(request, "reports/upload.html")


def processing_report_view(request, session_id):
    session = get_object_or_404(ReportSession, id=session_id)

    session.status = "processing"
    session.save()

    # 1. Extract text from every uploaded file
    for uploaded_file in session.files.all():
        process_single_uploaded_file(uploaded_file)

    # 2. Combine all extracted text
    all_extracted_text = get_all_extracted_text_for_session(session)

    # 3. Generate initial summary + create FAISS vector index
    if all_extracted_text:
        try:
            summary = generate_initial_summary_with_gemini(
                extracted_text=all_extracted_text,
                language=session.language,
            )
            session.initial_summary = summary

            rebuild_session_vector_index(session)

            session.status = "completed"

        except Exception as e:
            session.initial_summary = f"AI_PROCESSING_ERROR: {str(e)}"
            session.status = "failed"

    else:
        if session.language == "bn":
            session.initial_summary = (
                "Uploaded file থেকে readable text পাওয়া যায়নি। "
                "অনুগ্রহ করে পরিষ্কার PDF বা image upload করুন।"
            )
        else:
            session.initial_summary = (
                "No readable text was found in the uploaded file. "
                "Please upload a clear PDF or image."
            )

        session.status = "failed"

    session.save()

    # 4. Save initial AI summary as first assistant message
    if session.initial_summary:
        ChatMessage.objects.get_or_create(
            session=session,
            role="assistant",
            content=session.initial_summary,
        )

    # 5. Create default suggested questions
    create_default_suggested_questions(session)

    return redirect("chat_room", session_id=session.id)


def attach_report_view(request, session_id):
    """
    Attach more PDF/image reports into an existing chat session.
    This keeps the same chat memory and rebuilds FAISS index with old + new files.
    """

    session = get_object_or_404(ReportSession, id=session_id)

    if request.method != "POST":
        return redirect("chat_room", session_id=session.id)

    uploaded_files = request.FILES.getlist("files")
    camera_file = request.FILES.get("camera_file")

    all_files = []

    if uploaded_files:
        all_files.extend(uploaded_files)

    if camera_file:
        all_files.append(camera_file)

    if not all_files:
        messages.error(request, "Please select at least one file.")
        return redirect("chat_room", session_id=session.id)

    session.status = "processing"
    session.save()

    successful_files = []
    failed_files = []

    for file in all_files:
        file_type = get_file_type(file)

        uploaded_report = UploadedReportFile.objects.create(
            session=session,
            file=file,
            file_type=file_type,
            original_name=file.name,
            processing_status="pending",
        )

        process_single_uploaded_file(uploaded_report)

        if uploaded_report.processing_status == "completed":
            successful_files.append(uploaded_report.original_name)
        else:
            failed_files.append(uploaded_report.original_name)

    # Rebuild FAISS using old + new report files
    try:
        rebuild_session_vector_index(session)
        session.status = "completed"
    except Exception as e:
        session.status = "failed"

        if session.language == "bn":
            error_message = (
                f"নতুন রিপোর্ট upload হয়েছে, কিন্তু vector index update করতে সমস্যা হয়েছে: {str(e)}"
            )
        else:
            error_message = (
                f"New report was uploaded, but vector index update failed: {str(e)}"
            )

        ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=error_message,
            sources=[],
        )

        session.save()
        return redirect("chat_room", session_id=session.id)

    session.save()

    # Assistant confirmation message
    if session.language == "bn":
        if successful_files:
            file_list = ", ".join(successful_files)
            confirmation = (
                f"নতুন রিপোর্ট যোগ হয়েছে: {file_list}. "
                "এখন আপনি আগের এবং নতুন সব রিপোর্ট মিলিয়ে প্রশ্ন করতে পারেন।"
            )
        else:
            confirmation = (
                "নতুন রিপোর্ট process করা যায়নি। অনুগ্রহ করে পরিষ্কার PDF বা image upload করুন।"
            )
    else:
        if successful_files:
            file_list = ", ".join(successful_files)
            confirmation = (
                f"New report added: {file_list}. "
                "You can now ask questions using all uploaded reports."
            )
        else:
            confirmation = (
                "The new report could not be processed. Please upload a clear PDF or image."
            )

    if failed_files:
        if session.language == "bn":
            confirmation += f" তবে এই file process হয়নি: {', '.join(failed_files)}."
        else:
            confirmation += f" However, these files could not be processed: {', '.join(failed_files)}."

    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=confirmation,
        sources=[],
    )

    return redirect("chat_room", session_id=session.id)