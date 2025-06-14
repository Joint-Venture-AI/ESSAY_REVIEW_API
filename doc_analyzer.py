import os
import docx
import difflib
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

# Load API key from .env
load_dotenv()


# --- Document Extraction ---
def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    full_text = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(full_text)


# --- Gemini Setup ---
def initialize_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")  # Gemini 2.0 Flash


# --- Essay Type Classification ---
def classify_essay_type(model, essay_text):
    prompt = (
        "Classify the following essay into one of the types: "
        "Argumentative, Narrative, or Literary Analysis. Just return the type name.\n\n"
        f"{essay_text}"
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# --- Essay Analysis ---
def analyze_essay(model, essay_text, essay_type):
    base_prompt = (
        "Analyze this essay based on general writing quality (grammar, style, structure), "
        "and then check based on its type-specific criteria.\n\n"
    )

    if essay_type == "Argumentative":
        base_prompt += (
            "Check for thesis clarity, evidence support, counterarguments, "
            "and whether sources like Wikipedia are cited.\n\n"
        )
    elif essay_type == "Narrative":
        base_prompt += (
            "Check for vivid imagery, dialogue quality, and clear narrative arc.\n\n"
        )
    elif essay_type == "Literary Analysis":
        base_prompt += "Check for italicization of titles, use of present tense, and embedded quotations.\n\n"

    prompt = base_prompt + essay_text
    response = model.generate_content(prompt)
    return response.text.strip()


# --- Correction Tagging ---
def tag_differences(original_text, corrected_text):
    original_words = original_text.split()
    corrected_words = corrected_text.split()

    matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
    result = []

    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            result.extend(original_words[i1:i2])
        elif opcode == "replace":
            result.extend([f"[DELETE:{word}]" for word in original_words[i1:i2]])
            result.extend([f"[ADD:{word}]" for word in corrected_words[j1:j2]])
        elif opcode == "delete":
            result.extend([f"[DELETE:{word}]" for word in original_words[i1:i2]])
        elif opcode == "insert":
            result.extend([f"[ADD:{word}]" for word in corrected_words[j1:j2]])

    return " ".join(result)


# --- Source Authenticity Check ---
def check_unreliable_sources(text):
    unreliable_sources = ["wikipedia.org", "quora.com", "blogspot.com"]
    return [src for src in unreliable_sources if src in text.lower()]


# --- Grammar Correction ---
def correct_text(model, essay_text):
    prompt = (
        "Correct any grammar or sentence issues in the following text.\n"
        "Return only the corrected version.\n\n"
        f"{essay_text}"
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# --- Save Report ---
def save_report(essay_type, analysis, tagged, flagged_sources):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"essay_report_{timestamp}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Essay Type: {essay_type}\n\n")
        f.write("=== Analysis Report ===\n")
        f.write(analysis + "\n\n")
        f.write("=== Tagged Corrections ===\n")
        f.write(tagged + "\n\n")
        if flagged_sources:
            f.write(
                "⚠️ Unreliable sources detected: " + ", ".join(flagged_sources) + "\n"
            )
    return filename


# --- Main Execution ---
def run_essay_evaluation(file_path):
    # Extract and prepare
    essay_text = extract_text_from_docx(file_path)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Missing GOOGLE_API_KEY.")

    # Initialize model
    model = initialize_gemini(api_key)

    # Classify essay
    essay_type = classify_essay_type(model, essay_text)
    print(f"Essay Type: {essay_type}\n")

    # Multi-pass analysis
    general_and_specific_analysis = analyze_essay(model, essay_text, essay_type)
    print("=== Analysis Report ===\n")
    print(general_and_specific_analysis)

    # Grammar correction and tagging
    corrected_text = correct_text(model, essay_text)
    tagged = tag_differences(essay_text, corrected_text)
    print("\n=== Tagged Corrections ===\n")
    print(tagged)

    # Source check
    flagged = []
    if essay_type == "Argumentative":
        flagged = check_unreliable_sources(essay_text)
        if flagged:
            print("\n⚠️ Unreliable sources detected:", ", ".join(flagged))

    # Save output to file
    output_file = save_report(
        essay_type, general_and_specific_analysis, tagged, flagged
    )
    print(f"\n✅ Report saved as: {output_file}")


# Example usage:
run_essay_evaluation("essay_test.docx")
