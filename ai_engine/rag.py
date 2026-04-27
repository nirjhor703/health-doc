import os
from django.conf import settings

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS


def get_embeddings_model():
    """
    Gemini embedding model for RAG.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing. Please add it to your .env file.")

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.GEMINI_API_KEY
    )


def split_text_into_chunks(text):
    """
    Split extracted report text into chunks.
    Smaller chunks are better for report Q/A.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ".", "।", " ", ""]
    )

    return splitter.split_text(text)


def get_vectorstore_path(session_id):
    """
    Example:
    vectorstores/sessions/session_12
    or persistent disk path on Render.
    """
    base_dir = settings.VECTORSTORE_ROOT / "sessions"
    os.makedirs(base_dir, exist_ok=True)

    return str(base_dir / f"session_{session_id}")


def create_faiss_index_for_session(session):
    """
    Create FAISS vector index from all completed extracted files in a session.
    """

    all_text = ""

    for uploaded_file in session.files.all():
        if uploaded_file.extracted_text and uploaded_file.processing_status == "completed":
            all_text += f"\n\nFile: {uploaded_file.original_name}\n"
            all_text += uploaded_file.extracted_text

    all_text = all_text.strip()

    if not all_text:
        return None

    chunks = split_text_into_chunks(all_text)

    if not chunks:
        return None

    embeddings = get_embeddings_model()

    metadatas = []

    for index, chunk in enumerate(chunks):
        metadatas.append({
            "session_id": session.id,
            "chunk_index": index,
        })

    vectorstore = FAISS.from_texts(
        texts=chunks,
        embedding=embeddings,
        metadatas=metadatas,
    )

    vectorstore_path = get_vectorstore_path(session.id)
    vectorstore.save_local(vectorstore_path)

    return vectorstore_path


def retrieve_relevant_context(session, question, k=4):
    """
    Retrieve top-k relevant chunks from FAISS.
    If FAISS index is missing, fallback to full extracted text.
    """

    if not session.vector_index_path:
        return get_full_report_context(session)

    if not os.path.exists(session.vector_index_path):
        return get_full_report_context(session)

    embeddings = get_embeddings_model()

    try:
        vectorstore = FAISS.load_local(
            session.vector_index_path,
            embeddings,
            allow_dangerous_deserialization=True
        )

        docs = vectorstore.similarity_search(question, k=k)

        if not docs:
            return get_full_report_context(session)

        context = ""

        for i, doc in enumerate(docs, start=1):
            context += f"\n\nRelevant Section {i}:\n"
            context += doc.page_content

        return context.strip()

    except Exception as e:
        return f"RAG_RETRIEVAL_ERROR: {str(e)}\n\n{get_full_report_context(session)}"


def get_full_report_context(session):
    """
    Fallback context when vector search is unavailable.
    """

    context = ""

    for uploaded_file in session.files.all():
        if uploaded_file.extracted_text and uploaded_file.processing_status == "completed":
            context += f"\n\nFile: {uploaded_file.original_name}\n"
            context += uploaded_file.extracted_text

    return context.strip()