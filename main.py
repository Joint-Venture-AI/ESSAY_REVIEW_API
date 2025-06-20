from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import docx
import difflib
import google.generativeai as genai
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)
load_dotenv()


# --- Helpers ---
def extract_text_from_docx(file_stream):
    doc = docx.Document(file_stream)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])


def initialize_gemini(api_key):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


def classify_essay_type(model, essay_text):
    prompt = (
        "Classify the following essay into one of the types: Argumentative, Narrative, or Literary Analysis. Just return the type name.\n\n"
        + essay_text
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def analyze_essay(model, essay_text, essay_type):
    base_prompt = "Analyze this essay based on general writing quality (grammar, style, structure), and then check based on its type-specific criteria.\n\n"
    if essay_type == "Argumentative":
        base_prompt += "Check for thesis clarity, evidence support, counterarguments, and whether sources like Wikipedia are cited.\n\n"
    elif essay_type == "Narrative":
        base_prompt += (
            "Check for vivid imagery, dialogue quality, and clear narrative arc.\n\n"
        )
    elif essay_type == "Literary Analysis":
        base_prompt += "Check for italicization of titles, use of present tense, and embedded quotations.\n\n"
    response = model.generate_content(base_prompt + essay_text)
    return response.text.strip()


def correct_text(model, essay_text):
    prompt = (
        "Correct any grammar or sentence issues in the following text.\nReturn only the corrected version.\n\n"
        + essay_text
    )
    response = model.generate_content(prompt)
    return response.text.strip()


def tag_differences(original_text, corrected_text):
    original_words = original_text.split()
    corrected_words = corrected_text.split()
    matcher = difflib.SequenceMatcher(None, original_words, corrected_words)
    result = []
    for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
        if opcode == "equal":
            result.extend(original_words[i1:i2])
        elif opcode == "replace":
            result.extend([f"[DELETE:{w}]" for w in original_words[i1:i2]])
            result.extend([f"[ADD:{w}]" for w in corrected_words[j1:j2]])
        elif opcode == "delete":
            result.extend([f"[DELETE:{w}]" for w in original_words[i1:i2]])
        elif opcode == "insert":
            result.extend([f"[ADD:{w}]" for w in corrected_words[j1:j2]])
    return " ".join(result)


def check_unreliable_sources(text):
    unreliable = ["wikipedia.org", "quora.com", "blogspot.com"]
    return [src for src in unreliable if src in text.lower()]


# --- Single combined API route ---


@app.route("/api/full", methods=["POST"])
def full_analysis():
    try:
        if "docx_file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["docx_file"]
        if not file or not file.filename.endswith(".docx"):
            return jsonify({"error": "Invalid file format, must be .docx"}), 400

        essay_text = extract_text_from_docx(file.stream)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)

        # Step 1: Classify essay type
        essay_type = classify_essay_type(model, essay_text)

        # Step 2: Analyze essay with type-specific checks
        analysis = analyze_essay(model, essay_text, essay_type)

        # Step 3: Correct grammar and sentence issues
        corrected_text = correct_text(model, essay_text)

        # Step 4: Tag differences between original and corrected
        tagged_diff = tag_differences(essay_text, corrected_text)

        # Step 5: Check unreliable sources if argumentative essay
        unreliable_sources = (
            check_unreliable_sources(essay_text)
            if essay_type == "Argumentative"
            else []
        )

        response = {
            "essay_type": essay_type,
            "analysis": analysis,
            "corrected_text": corrected_text,
            "tagged_differences": tagged_diff,
            "unreliable_sources": unreliable_sources,
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
