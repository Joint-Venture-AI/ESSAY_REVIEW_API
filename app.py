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


def compare_two_docs(doc1_stream, doc2_stream):
    text1 = extract_text_from_docx(doc1_stream)
    text2 = extract_text_from_docx(doc2_stream)
    tagged_diff = tag_differences(text1, text2)
    return text1, text2, tagged_diff


# --- API Routes ---


@app.route("/api/classify", methods=["POST"])
def classify_essay():
    try:
        if "docx_file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["docx_file"]
        if not file or not file.filename.endswith(".docx"):
            return jsonify({"error": "Invalid file format, must be .docx"}), 400

        essay_text = extract_text_from_docx(file.stream)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)
        essay_type = classify_essay_type(model, essay_text)

        return jsonify({"essay_type": essay_type}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze_essay_api():
    try:
        if "docx_file" not in request.files or "essay_type" not in request.form:
            return jsonify({"error": "Missing docx_file or essay_type"}), 400

        file = request.files["docx_file"]
        essay_type = request.form["essay_type"]
        if not file or not file.filename.endswith(".docx"):
            return jsonify({"error": "Invalid file format, must be .docx"}), 400
        if essay_type not in ["Argumentative", "Narrative", "Literary Analysis"]:
            return jsonify({"error": "Invalid essay_type"}), 400

        essay_text = extract_text_from_docx(file.stream)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)
        analysis = analyze_essay(model, essay_text, essay_type)
        sources = (
            check_unreliable_sources(essay_text)
            if essay_type == "Argumentative"
            else []
        )

        return jsonify({"analysis": analysis, "unreliable_sources": sources}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/correct", methods=["POST"])
def correct_essay():
    try:
        if "docx_file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["docx_file"]
        if not file or not file.filename.endswith(".docx"):
            return jsonify({"error": "Invalid file format, must be .docx"}), 400

        essay_text = extract_text_from_docx(file.stream)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)
        corrected = correct_text(model, essay_text)
        tagged = tag_differences(essay_text, corrected)

        return jsonify({"corrected_text": corrected, "tagged_differences": tagged}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/full-analysis", methods=["POST"])
def full_analysis():
    try:
        if "docx_file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["docx_file"]
        if not file or not file.filename.endswith(".docx"):
            return jsonify({"error": "Invalid file format, must be .docx"}), 400

        essay_text = extract_text_from_docx(file.stream)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)
        essay_type = classify_essay_type(model, essay_text)
        analysis = analyze_essay(model, essay_text, essay_type)
        corrected = correct_text(model, essay_text)
        tagged = tag_differences(essay_text, corrected)
        sources = (
            check_unreliable_sources(essay_text)
            if essay_type == "Argumentative"
            else []
        )

        response = {
            "essay_type": essay_type,
            "analysis": analysis,
            "corrected_text": corrected,
            "tagged_differences": tagged,
            "unreliable_sources": sources,
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/compare", methods=["POST"])
def compare_essays():
    try:
        if "docx_file_1" not in request.files or "docx_file_2" not in request.files:
            return (
                jsonify({"error": "Both docx_file_1 and docx_file_2 are required."}),
                400,
            )

        file1 = request.files["docx_file_1"]
        file2 = request.files["docx_file_2"]
        if not file1.filename.endswith(".docx") or not file2.filename.endswith(".docx"):
            return jsonify({"error": "Files must be in .docx format."}), 400

        text1 = extract_text_from_docx(file1.stream)
        text2 = extract_text_from_docx(file2.stream)

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return jsonify({"error": "Missing API Key"}), 500

        model = initialize_gemini(api_key)

        # Section 1: High-level Analysis Summary
        prompt = (
            "Compare the following two versions of an essay. "
            "Give a short analytical summary of key improvements, tone, structure, and clarity. "
            "Respond in 2-3 sentences.\n\n"
            "Version 1:\n" + text1 + "\n\nVersion 2:\n" + text2
        )
        summary_response = model.generate_content(prompt)
        analysis_summary = summary_response.text.strip()

        # Section 2: Key Changes (diffed paragraphs)
        para1 = text1.split("\n")
        para2 = text2.split("\n")
        max_len = max(len(para1), len(para2))
        changes = []

        for i in range(max_len):
            p1 = para1[i] if i < len(para1) else ""
            p2 = para2[i] if i < len(para2) else ""
            if p1.strip() != p2.strip():
                diff = tag_differences(p1, p2)
                changes.append({"paragraph_index": i + 1, "change": diff})

        return (
            jsonify({"analysis_summary": analysis_summary, "key_changes": changes}),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
