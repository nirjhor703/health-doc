from pypdf import PdfReader


def extract_text_from_pdf(file_path):
    """
    Extract text from a PDF file using pypdf.
    Works best for digital PDFs, not scanned image PDFs.
    """
    text = ""

    try:
        reader = PdfReader(file_path)

        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text()

            if page_text:
                text += f"\n\n--- Page {page_number} ---\n"
                text += page_text

        return text.strip()

    except Exception as e:
        return f"PDF_TEXT_EXTRACTION_ERROR: {str(e)}"


def clean_extracted_text(text):
    """
    Basic text cleanup.
    """
    if not text:
        return ""

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        line = line.strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)