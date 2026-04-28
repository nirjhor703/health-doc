import time
from django.conf import settings
from google import genai
from google.genai import types


def get_gemini_client():
    """
    Create Gemini client using API key from Django settings.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing. Please add it to your .env file.")

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _guess_image_mime_type(file_path):
    """
    Guess image MIME type from file extension.
    """
    file_path = file_path.lower()

    if file_path.endswith(".png"):
        return "image/png"

    if file_path.endswith(".webp"):
        return "image/webp"

    if file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
        return "image/jpeg"

    return "image/jpeg"


def _generate_with_retry(client, prompt_or_contents, task_name="GEMINI_TASK"):
    """
    Common Gemini retry helper.
    Tries multiple Gemini models in order.
    If one model quota is exhausted, unavailable, or unsupported,
    it moves to the next model so users do not get stuck easily.
    """

    models_to_try = [
        # Best current fallback from your quota table: 0 / 500 RPD
        "gemini-3.1-flash-lite-preview",

        # Strong multimodal model, but your current free quota may be low
        "gemini-3-flash-preview",

        # Older but still useful if quota available
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",

        # Deprecated fallback only; not recommended as primary
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
    ]

    last_error = None

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                print(f"{task_name}: trying model {model_name}")

                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt_or_contents,
                )

                if response.text:
                    print(f"{task_name}: success with model {model_name}")
                    return response.text.strip()

                return ""

            except Exception as e:
                last_error = e
                error_text = str(e)

                print(f"{task_name}: error on {model_name}: {error_text}")

                # Quota/rate limit: do not keep retrying same model. Try next model.
                if (
                    "429" in error_text
                    or "RESOURCE_EXHAUSTED" in error_text
                    or "quota" in error_text.lower()
                    or "rate limit" in error_text.lower()
                ):
                    break

                # Model not found / unsupported for this API or input type: try next model.
                if (
                    "404" in error_text
                    or "NOT_FOUND" in error_text
                    or "not found" in error_text.lower()
                    or "not supported" in error_text.lower()
                ):
                    break

                # Temporary overload: retry same model once, then continue.
                if "503" in error_text or "UNAVAILABLE" in error_text:
                    time.sleep(2 + attempt * 2)
                    continue

                # Other unexpected errors: try next model instead of crashing immediately.
                break

    return (
        f"{task_name}_FAILED_AFTER_ALL_MODELS: {str(last_error)}"
    )


def extract_text_from_image_with_gemini(image_path):
    """
    Extract readable text from an image using Gemini Vision.
    Used for uploaded medical report images or camera captures.
    """

    client = get_gemini_client()

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    prompt = """
You are an OCR and medical/document text extraction assistant.

Task:
Extract all readable text from this image.

Rules:
- Do not diagnose.
- Do not explain the report/document.
- Only extract the visible/readable text.
- Preserve headings, tables, test names, values, units, reference ranges, dates, names, phone numbers, and labels.
- If a value is unclear, write [unclear].
- Keep the output clean and structured.
"""

    contents = [
        types.Part.from_bytes(
            data=image_bytes,
            mime_type=_guess_image_mime_type(image_path),
        ),
        prompt,
    ]

    return _generate_with_retry(
        client=client,
        prompt_or_contents=contents,
        task_name="GEMINI_IMAGE_EXTRACTION",
    )


def extract_text_from_pdf_with_gemini(pdf_path):
    """
    Extract readable text from a PDF using Gemini.
    Useful for scanned/image-based PDFs where pypdf cannot extract text.
    """

    client = get_gemini_client()

    with open(pdf_path, "rb") as pdf_file:
        pdf_bytes = pdf_file.read()

    prompt = """
You are an OCR and document extraction assistant.

Task:
Extract all readable text from this PDF document.

Rules:
- Do not explain the document.
- Do not diagnose.
- Only extract visible/readable text.
- Preserve headings, tables, names, values, units, dates, phone numbers, and important labels.
- If a value is unclear, write [unclear].
- Keep the output clean and structured.
"""

    contents = [
        types.Part.from_bytes(
            data=pdf_bytes,
            mime_type="application/pdf",
        ),
        prompt,
    ]

    return _generate_with_retry(
        client=client,
        prompt_or_contents=contents,
        task_name="GEMINI_PDF_EXTRACTION",
    )


def generate_initial_summary_with_gemini(extracted_text, language="en"):
    """
    Generate a short, safe, user-friendly initial summary from extracted document/report text.
    Initial summary should be structured because it is the first report overview.
    """

    client = get_gemini_client()

    if language == "bn":
        language_instruction = """
Respond only in natural Bangla/Banglish.
Use very simple words so a normal person can understand.
Avoid complicated medical jargon.
Do not mix English except common medical test names like CBC, ESR, Hemoglobin, Platelet, LDL, HDL, HbA1c.
"""
        output_format = """
Output format must be exactly:

1. রিপোর্টের সংক্ষিপ্ত সারাংশ:
খুব সহজ ভাষায় 2-4 লাইনে report/document-er summary লিখুন.

2. কম / বেশি পাওয়া বিষয়:
Medical report হলে list আকারে শুধু কম/বেশি/borderline value গুলো লিখুন.
প্রতিটি point ছোট রাখুন.
যদি কম/বেশি value স্পষ্ট না থাকে, লিখুন: "এই রিপোর্টে কম/বেশি value স্পষ্টভাবে পাওয়া যায়নি।"

3. গুরুত্বপূর্ণ বিষয়:
2-4টি সহজ point লিখুন।
Doctor consult করার কথা safe ভাবে বলুন।
"""
    else:
        language_instruction = """
Respond only in simple English.
Use very easy words so a normal person can understand.
Avoid complicated medical jargon.
Do not use Bangla headings or Bangla text.
"""
        output_format = """
Output format must be exactly:

1. Report Summary:
Write the report/document summary in 2-4 very simple lines.

2. Low / High Values:
If this is a medical report, list only the low/high/borderline values.
Keep each point short.
If no low/high values are clearly found, write: "No clearly low or high values were found in this report."

3. Important Notes:
Write 2-4 simple points.
Safely mention consulting a licensed doctor.
"""

    prompt = f"""
You are Health-Doc Virtual Assistant.

Your job:
Summarize the uploaded document/report in very simple language.

Important safety rules:
- If the document is a medical report, explain it simply.
- Do not diagnose disease.
- Do not prescribe medicine.
- Do not suggest exact treatment.
- Do not decide emergency status.
- If this is not a medical report, clearly say that it does not appear to be a medical report.
- Be friendly and helpful.
- Keep the answer short and useful.
- Do not add suggested questions at the end.
- Do not use markdown tables.
- Do not over-explain.

Writing style:
- Write for a normal person, not a doctor.
- Use short sentences.
- Avoid confusing or over-detailed explanation.
- Mention only the most important findings.

{output_format}

{language_instruction}

Extracted document text:
{extracted_text}
"""

    return _generate_with_retry(
        client=client,
        prompt_or_contents=prompt,
        task_name="GEMINI_SUMMARY",
    )


def generate_chat_answer_with_gemini(
    report_context,
    user_question,
    language="en",
    chat_history=None,
):
    """
    Generate a smart safe chat answer.
    The answer length and structure should depend on the user's question.

    Examples:
    - "What doctor should I consult?" -> 1-3 lines only.
    - "What is hemoglobin?" -> short simple answer.
    - "Summarize report" -> structured sections.
    - "Which values are high/low?" -> short bullet list.
    """

    client = get_gemini_client()

    if chat_history is None:
        chat_history = []

    if language == "bn":
        language_instruction = """
Respond only in natural Bangla/Banglish.
Use very simple words so a normal person can understand.
Avoid complicated medical jargon.
Do not mix English except common medical test names like CBC, ESR, Hemoglobin, Platelet, LDL, HDL, HbA1c.
"""
        missing_info_text = "এই তথ্যটি uploaded report/document-এ স্পষ্টভাবে পাওয়া যাচ্ছে না।"
        smart_answer_policy = """
Answer size policy:
- যদি user খুব simple question করে, 1-3 লাইনে answer দিন.
- যদি user doctor/specialist জানতে চায়, শুধু specialist name + short reason দিন.
- যদি user summary চায়, 3 section format ব্যবহার করুন.
- যদি user কম/বেশি value জানতে চায়, শুধু bullet list দিন.
- যদি user lifestyle tips চায়, 3-5টি simple general tips দিন.
- অপ্রয়োজনীয় section add করবেন না.
- সব answer-এ একই format use করবেন না.
- User যতটুকু জানতে চেয়েছে, শুধু ততটুকুই answer দিন.

For structured summary only, use exactly:
1. রিপোর্টের সংক্ষিপ্ত সারাংশ:
2. কম / বেশি পাওয়া বিষয়:
3. গুরুত্বপূর্ণ বিষয়:

For normal/simple questions:
Do NOT use numbered sections.
Do NOT write "রিপোর্ট থেকে পাওয়া তথ্য" unless user specifically asks for details.
"""
    else:
        language_instruction = """
Respond only in simple English.
Use very easy words so a normal person can understand.
Avoid complicated medical jargon.
Do not use Bangla headings or Bangla text.
"""
        missing_info_text = "This information is not clearly present in the uploaded report/document."
        smart_answer_policy = """
Answer size policy:
- If the user asks a simple question, answer in 1-3 lines.
- If the user asks what doctor/specialist to consult, give only the specialist name + short reason.
- If the user asks for a summary, use the 3-section format.
- If the user asks which values are low/high, give only a bullet list.
- If the user asks for lifestyle tips, give 3-5 simple general tips.
- Do not add unnecessary sections.
- Do not use the same format for every answer.
- Answer only what the user asked.

For structured summary only, use exactly:
1. Report Summary:
2. Low / High Values:
3. Important Notes:

For normal/simple questions:
Do NOT use numbered sections.
Do NOT write "Information Found in the Report" unless the user specifically asks for details.
"""

    formatted_history = ""

    for item in chat_history:
        role = item.get("role", "")
        content = item.get("content", "")
        formatted_history += f"\n{role}: {content}\n"

    prompt = f"""
You are Health-Doc Virtual Assistant, a friendly medical report/document explanation assistant.

Your main job:
- Answer the user's question based on the uploaded report/document text.
- If the document is medical, explain it in very simple language.
- If the document is not medical, answer only from the uploaded document.
- Use recent conversation history only to understand context.

Medical safety rules:
- Do not diagnose disease.
- Do not prescribe medicine.
- Do not suggest exact treatment.
- Do not decide emergency status.
- Do not say the user definitely has a disease.
- Do not replace a licensed doctor.
- You may suggest what type of doctor/specialist may be relevant using cautious wording.
- You may provide general lifestyle education, but not strict medical instructions.

Specialist suggestion rule:
- Heart, ECG, chest pain, cholesterol, blockage concern -> Cardiologist
- Diabetes, HbA1c, sugar, thyroid, hormones -> Endocrinologist
- Kidney, creatinine, urea, urine protein -> Nephrologist
- Liver enzyme, bilirubin, hepatitis -> Hepatologist or Gastroenterologist
- Blood count, anemia, hemoglobin, platelet, WBC -> Hematologist or Medicine Specialist
- Urine infection or urinary symptoms -> Urologist or Medicine Specialist
- Stomach, digestion, gastric, colon -> Gastroenterologist
- Pregnancy-related report -> Gynecologist
- Child patient report -> Pediatrician
- Unclear or mixed report -> Medicine Specialist / General Physician

Answering rules:
- Use only the uploaded report/document text and safe general education.
- If the answer is not present in the report/document, say: "{missing_info_text}"
- Keep the answer short, simple, and useful.
- Do not use markdown tables.
- Do not add suggested questions at the end.
- If the answer is medical, include a very short safety reminder only when necessary.
- Do not repeat the same report details in every answer.
- First understand the user's question, then decide how much answer is needed.

Writing style:
- Write for a normal person, not a doctor.
- Use short sentences.
- Avoid confusing medical jargon.
- Do not over-explain.
- Mention only the most important points.
- Keep the tone friendly and calm.

{smart_answer_policy}

{language_instruction}

Uploaded report/document text:
{report_context}

Recent conversation history:
{formatted_history}

User question:
{user_question}
"""

    return _generate_with_retry(
        client=client,
        prompt_or_contents=prompt,
        task_name="GEMINI_CHAT",
    )