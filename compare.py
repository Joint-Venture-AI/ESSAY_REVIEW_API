from flask import Flask, request, jsonify
import os
import google.generativeai as genai
from docx import Document
from dotenv import load_dotenv
from difflib import ndiff

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-pro')  # use a more accurate model if needed

def extract_lines(file):
    if file.filename.endswith('.docx'):
        doc = Document(file)
        return [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    elif file.filename.endswith('.txt'):
        return file.read().decode('utf-8').splitlines()
    elif file.filename.endswith('.pdf'):
        from PyPDF2 import PdfReader
        pdf = PdfReader(file)
        all_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        return all_text.splitlines()
    else:
        return []

def tag_word_diff(line1, line2):
    diff = list(ndiff(line1.split(), line2.split()))
    tagged_line1, tagged_line2 = [], []
    
    for word in diff:
        if word.startswith('- '):
            tagged_line1.append(f"<del>{word[2:]}</del>")
        elif word.startswith('+ '):
            tagged_line2.append(f"<ins>{word[2:]}</ins>")
        elif word.startswith('  '):
            word_clean = word[2:]
            tagged_line1.append(word_clean)
            tagged_line2.append(word_clean)
    return ' '.join(tagged_line1), ' '.join(tagged_line2)

@app.route('/compare-essays', methods=['POST'])
def compare_essays():
    if 'essay1' not in request.files or 'essay2' not in request.files:
        return jsonify({'error': 'Please upload both essay1 and essay2 files'}), 400

    file1 = request.files['essay1']
    file2 = request.files['essay2']

    lines1 = extract_lines(file1)
    lines2 = extract_lines(file2)

    max_len = max(len(lines1), len(lines2))
    comparison_results = []
    all_text1 = []
    all_text2 = []

    try:
        for i in range(max_len):
            line1 = lines1[i] if i < len(lines1) else ""
            line2 = lines2[i] if i < len(lines2) else ""

            tagged1, tagged2 = tag_word_diff(line1, line2)
            all_text1.append(line1)
            all_text2.append(line2)

            prompt = f"""
Compare the following lines from two essays and describe what changed.

Essay 1:
{line1}

Essay 2:
{line2}

Give a short, clear analysis of the differences.
"""

            response = model.generate_content(prompt)
            comparison_results.append({
                'line_number': i + 1,
                'essay1': tagged1,
                'essay2': tagged2,
                'analysis': response.text.strip()
            })

        # Generate final summary
        full_essay1 = "\n".join(all_text1)
        full_essay2 = "\n".join(all_text2)
        summary_prompt = f"""
You are given two essays. Provide a concise summary that highlights the key differences in tone, structure, ideas, and writing style.

Essay 1:
{full_essay1}

Essay 2:
{full_essay2}

Return the analysis in 3-5 bullet points.
"""

        summary_response = model.generate_content(summary_prompt)

        return jsonify({
            'status': 'success',
            'line_by_line_comparison': comparison_results,
            'final_summary': summary_response.text.strip()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
