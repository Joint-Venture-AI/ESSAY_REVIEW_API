import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import docx
import google.generativeai as genai

# Load API key from .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

app = Flask(__name__)

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def create_prompt(essay_text):
    return f"""
You are an academic writing assistant.

Analyze the following essay and respond with a JSON object that includes:
1. The type of essay: (One of: 'Argumentative', 'Narrative', 'Literary Analysis', or 'Other').
2. The corrected version of the essay using tracked changes:
   - If a word or phrase needs to be deleted, surround it with <deletion>...<\deletion>.
   - If something should be added, wrap the new word(s) in <addition>...<\addition>.

Only return a valid JSON object like:
{{
  "essay_type": "Argumentative",
  "corrected_essay": "Your corrected text with <addition>additions</addition> and <deletion>deletions</deletion>"
}}

Essay:
\"\"\"
{essay_text}
\"\"\"
"""

@app.route('/analyze_essay', methods=['POST'])
def analyze_essay():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename.endswith('.docx'):
        return jsonify({'error': 'Only .docx files are supported'}), 400

    try:
        essay_text = extract_text_from_docx(file)
        prompt = create_prompt(essay_text)

        response = model.generate_content(prompt)
        # Attempt to extract JSON from Gemini output
        import json
        import re

        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            result_json = json.loads(match.group())
            return jsonify(result_json)
        else:
            return jsonify({'error': 'Invalid response format from Gemini'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
