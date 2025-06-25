import os
import re
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai
from datetime import datetime
import tempfile
from werkzeug.utils import secure_filename
from docx import Document
from dotenv import load_dotenv
import difflib
from typing import List, Dict, Tuple
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import io
from flask import send_file

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in environment variables. Please add it to your .env file.")
    # For demo purposes, we'll continue without it but provide fallback responses

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

# Essay type classifications
ESSAY_TYPES = {
    'argumentative': {
        'keywords': ['argue', 'thesis', 'evidence', 'counterargument', 'claim', 'support', 'oppose', 'debate'],
        'criteria': [
            'Clear thesis statement',
            'Strong evidence and examples',
            'Counterargument acknowledgment',
            'Logical flow of arguments',
            'Source credibility check'
        ]
    },
    'narrative': {
        'keywords': ['story', 'experience', 'happened', 'remember', 'narrative', 'personal', 'journey'],
        'criteria': [
            'Clear narrative arc',
            'Vivid imagery and descriptions',
            'Dialogue quality',
            'Character development',
            'Chronological flow'
        ]
    },
    'literary_analysis': {
        'keywords': ['analyze', 'literary', 'author', 'character', 'theme', 'symbolism', 'literary device'],
        'criteria': [
            'Present tense usage',
            'Proper title italicization',
            'Quote integration',
            'Literary device identification',
            'Theme analysis depth'
        ]
    },
    'expository': {
        'keywords': ['explain', 'inform', 'describe', 'process', 'how to', 'definition'],
        'criteria': [
            'Clear explanations',
            'Logical organization',
            'Supporting details',
            'Objective tone',
            'Factual accuracy'
        ]
    }
}

class DocumentProcessor:
    @staticmethod
    def read_docx(file_path):
        """Read DOCX file and return text content with paragraph structure"""
        try:
            doc = Document(file_path)
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():  # Only include non-empty paragraphs
                    paragraphs.append(para.text.strip())
            return {
                'text': '\n\n'.join(paragraphs),
                'paragraphs': paragraphs,
                'paragraph_count': len(paragraphs)
            }
        except Exception as e:
            raise Exception(f"Error reading DOCX file: {str(e)}")
    
    @staticmethod
    def read_txt(file_path):
        """Read TXT file and return text content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
                return {
                    'text': content,
                    'paragraphs': paragraphs,
                    'paragraph_count': len(paragraphs)
                }
        except Exception as e:
            raise Exception(f"Error reading TXT file: {str(e)}")

class EssayAnalyzer:
    def __init__(self):
        self.model = model
    
    def classify_essay_type(self, text):
        """Classify the essay type based on content analysis"""
        text_lower = text.lower()
        scores = {}
        
        for essay_type, data in ESSAY_TYPES.items():
            score = sum(1 for keyword in data['keywords'] if keyword in text_lower)
            scores[essay_type] = score
        
        # Get the type with highest score
        primary_type = max(scores, key=scores.get) if scores else 'expository'
        
        # Check for hybrid essays (multiple high scores)
        high_scores = [t for t, s in scores.items() if s >= max(scores.values()) * 0.7] if scores else []
        
        return {
            'primary_type': primary_type,
            'hybrid_types': high_scores if len(high_scores) > 1 else [],
            'confidence': scores[primary_type] / len(ESSAY_TYPES[primary_type]['keywords']) if ESSAY_TYPES.get(primary_type, {}).get('keywords') else 0.5
        }
    
    def analyze_grammar_and_style(self, text):
        """Analyze grammar, style, and structure using Gemini AI"""
        if not self.model:
            return self._fallback_analysis(text)
            
        prompt = f"""
        Please analyze the following essay for grammar, style, and structure issues. 
        Provide specific suggestions for improvement in JSON format with the following structure:
        {{
            "grammar_issues": [
                {{"issue": "description", "suggestion": "correction", "line": "approximate line number"}}
            ],
            "style_issues": [
                {{"issue": "description", "suggestion": "improvement", "line": "approximate line number"}}
            ],
            "structure_issues": [
                {{"issue": "description", "suggestion": "improvement", "section": "section name"}}
            ],
            "overall_score": "score out of 100",
            "strengths": ["list of strengths"],
            "priority_improvements": ["top 3 improvements needed"]
        }}
        
        Essay text:
        {text[:2000]}...
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                return self._fallback_analysis(text)
        except Exception as e:
            print(f"Error in AI analysis: {e}")
            return self._fallback_analysis(text)
    
    def analyze_essay_specific_criteria(self, text, essay_type):
        """Analyze essay based on specific type criteria"""
        if not self.model:
            return self._fallback_type_analysis(essay_type)
            
        criteria = ESSAY_TYPES.get(essay_type, {}).get('criteria', [])
        
        prompt = f"""
        Analyze this {essay_type} essay based on these specific criteria: {', '.join(criteria)}.
        Also check for source authenticity issues (like Wikipedia usage in argumentative essays).
        
        Provide analysis in JSON format:
        {{
            "criteria_analysis": [
                {{"criterion": "name", "score": "1-10", "feedback": "detailed feedback"}}
            ],
            "source_issues": [
                {{"issue": "description", "suggestion": "improvement"}}
            ],
            "type_specific_suggestions": ["list of suggestions specific to {essay_type} essays"]
        }}
        
        Essay text:
        {text[:2000]}...
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start:json_end]
                return json.loads(json_str)
            else:
                return self._fallback_type_analysis(essay_type)
        except Exception as e:
            print(f"Error in type-specific analysis: {e}")
            return self._fallback_type_analysis(essay_type)
    
    def generate_interactive_suggestions(self, text):
        """Generate interactive suggestions with specific word-level changes"""
        if not self.model:
            return self._fallback_suggestions(text)
            
        # Split text into smaller chunks for better processing
        words = text.split()
        chunk_size = 500
        all_suggestions = []
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            chunk_start_pos = len(' '.join(words[:i]))
            
            prompt = f"""
            Analyze the following essay excerpt and provide specific word-level and sentence-level suggestions for improvement.
            For each suggestion, provide the exact original text and the suggested replacement.
            
            Provide the response in JSON format:
            {{
                "suggestions": [
                    {{
                        "id": "unique_id_{i}",
                        "type": "grammar|spelling|style|structure",
                        "original": "exact original text to be replaced",
                        "suggested": "suggested replacement text",
                        "reason": "explanation for the change",
                        "position": {{
                            "start": start_character_position,
                            "end": end_character_position
                        }},
                        "severity": "high|medium|low"
                    }}
                ]
            }}
            
            Essay excerpt:
            {chunk_text}
            
            Focus on:
            1. Spelling errors
            2. Grammar mistakes
            3. Word choice improvements
            4. Sentence structure
            5. Clarity and flow
            """
            
            try:
                response = self.model.generate_content(prompt)
                response_text = response.text
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = response_text[json_start:json_end]
                    chunk_result = json.loads(json_str)
                    
                    # Adjust positions for the full text
                    for suggestion in chunk_result.get('suggestions', []):
                        suggestion['position']['start'] += chunk_start_pos
                        suggestion['position']['end'] += chunk_start_pos
                        suggestion['id'] = f"suggestion_{len(all_suggestions) + 1}"
                    
                    all_suggestions.extend(chunk_result.get('suggestions', []))
                    
            except Exception as e:
                print(f"Error processing chunk {i}: {e}")
                continue
        
        return {"suggestions": all_suggestions[:20]}  # Limit to 20 suggestions for performance
    
    def _fallback_analysis(self, text):
        """Fallback analysis when AI fails"""
        word_count = len(text.split())
        return {
            "grammar_issues": [
                {"issue": "AI analysis temporarily unavailable", "suggestion": "Please check your API configuration", "line": "N/A"}
            ],
            "style_issues": [
                {"issue": "Manual review recommended", "suggestion": "Consider sentence variety and word choice", "line": "N/A"}
            ],
            "structure_issues": [
                {"issue": "Check essay organization", "suggestion": "Ensure clear introduction, body, and conclusion", "section": "Overall"}
            ],
            "overall_score": "75",
            "strengths": [
                f"Essay contains {word_count} words",
                "Content has been provided for analysis",
                "Structure appears to follow basic essay format"
            ],
            "priority_improvements": [
                "Configure AI API key for detailed analysis",
                "Review grammar and spelling manually",
                "Check essay structure and flow"
            ]
        }
    
    def _fallback_type_analysis(self, essay_type):
        """Fallback type-specific analysis"""
        return {
            "criteria_analysis": [
                {"criterion": f"{essay_type} structure", "score": "7", "feedback": "AI analysis unavailable - manual review recommended"},
                {"criterion": "Content relevance", "score": "8", "feedback": "Content appears relevant to essay type"},
                {"criterion": "Organization", "score": "7", "feedback": "Basic organization present"}
            ],
            "source_issues": [
                {"issue": "Unable to verify sources", "suggestion": "Manually check source credibility and citations"}
            ],
            "type_specific_suggestions": [
                f"Review {essay_type} essay guidelines and requirements",
                "Ensure all criteria for this essay type are met",
                "Consider peer review for additional feedback"
            ]
        }
    
    def _fallback_suggestions(self, text):
        """Fallback suggestions when AI fails"""
        # Create some basic suggestions based on common issues
        suggestions = []
        
        # Check for common issues
        if "i " in text.lower():
            suggestions.append({
                "id": "suggestion_1",
                "type": "style",
                "original": "i",
                "suggested": "I",
                "reason": "Capitalize the pronoun 'I'",
                "position": {"start": text.lower().find("i "), "end": text.lower().find("i ") + 1},
                "severity": "medium"
            })
        
        if text.count('.') < 3:
            suggestions.append({
                "id": "suggestion_2",
                "type": "structure",
                "original": "Short essay",
                "suggested": "Consider expanding with more detailed examples",
                "reason": "Essay appears to be quite short",
                "position": {"start": 0, "end": 0},
                "severity": "low"
            })
        
        return {"suggestions": suggestions}

# Initialize analyzer and processor
analyzer = EssayAnalyzer()
doc_processor = DocumentProcessor()

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze_essay():
    try:
        data = request.get_json()
        essay_text = data.get('text', '')
        
        if not essay_text.strip():
            return jsonify({'error': 'No essay text provided'}), 400
        
        if len(essay_text.strip()) < 50:
            return jsonify({'error': 'Essay is too short for meaningful analysis'}), 400
        
        # Step 1: Classify essay type
        classification = analyzer.classify_essay_type(essay_text)
        
        # Step 2: General analysis (grammar, style, structure)
        general_analysis = analyzer.analyze_grammar_and_style(essay_text)
        
        # Step 3: Essay-specific analysis
        specific_analysis = analyzer.analyze_essay_specific_criteria(
            essay_text, classification['primary_type']
        )
        
        # Step 4: Generate interactive suggestions
        interactive_suggestions = analyzer.generate_interactive_suggestions(essay_text)
        
        # Compile final results
        results = {
            'classification': classification,
            'analysis': {
                'general': general_analysis,
                'specific': specific_analysis
            },
            'interactive_suggestions': interactive_suggestions,
            'timestamp': datetime.now().isoformat(),
            'word_count': len(essay_text.split()),
            'character_count': len(essay_text)
        }
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Error in analysis: {e}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if file and file.filename.lower().endswith(('.txt', '.docx')):
            filename = secure_filename(file.filename)
            
            # Save file temporarily
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            file.save(temp_path)
            
            try:
                # Read file content based on type
                if filename.lower().endswith('.txt'):
                    content = doc_processor.read_txt(temp_path)
                else:  # .docx
                    content = doc_processor.read_docx(temp_path)
                
                # Clean up temp file
                os.unlink(temp_path)
                
                return jsonify({
                    'text': content['text'],
                    'filename': filename,
                    'paragraphs': content['paragraphs'],
                    'paragraph_count': content['paragraph_count']
                })
                
            except Exception as e:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return jsonify({'error': f'Error processing file: {str(e)}'}), 400
        
        return jsonify({'error': 'Unsupported file type. Please upload TXT or DOCX files.'}), 400
        
    except Exception as e:
        print(f"Error in file upload: {e}")
        return jsonify({'error': 'File upload failed'}), 500

@app.route('/compare', methods=['POST'])
def compare_documents():
    try:
        if 'file1' not in request.files or 'file2' not in request.files:
            return jsonify({'error': 'Two files are required for comparison'}), 400
        
        file1 = request.files['file1']
        file2 = request.files['file2']
        
        if file1.filename == '' or file2.filename == '':
            return jsonify({'error': 'Please select both files'}), 400
        
        # Check file types
        allowed_extensions = ('.txt', '.docx')
        if not (file1.filename.lower().endswith(allowed_extensions) and 
                file2.filename.lower().endswith(allowed_extensions)):
            return jsonify({'error': 'Both files must be TXT or DOCX format'}), 400
        
        # Save files temporarily
        filename1 = secure_filename(file1.filename)
        filename2 = secure_filename(file2.filename)
        temp_path1 = os.path.join(tempfile.gettempdir(), f"comp1_{filename1}")
        temp_path2 = os.path.join(tempfile.gettempdir(), f"comp2_{filename2}")
        
        file1.save(temp_path1)
        file2.save(temp_path2)
        
        try:
            # Read both files
            if filename1.lower().endswith('.txt'):
                content1 = doc_processor.read_txt(temp_path1)
            else:
                content1 = doc_processor.read_docx(temp_path1)
            
            if filename2.lower().endswith('.txt'):
                content2 = doc_processor.read_txt(temp_path2)
            else:
                content2 = doc_processor.read_docx(temp_path2)
            
            # Perform comparison
            comparison_results = DocumentComparator().compare_documents(
                content1, content2, filename1, filename2
            )
            
            # Clean up temp files
            os.unlink(temp_path1)
            os.unlink(temp_path2)
            
            return jsonify({
                'comparison': comparison_results,
                'file1_name': filename1,
                'file2_name': filename2,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            # Clean up temp files on error
            for temp_path in [temp_path1, temp_path2]:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            return jsonify({'error': f'Error processing files: {str(e)}'}), 400
        
    except Exception as e:
        print(f"Error in document comparison: {e}")
        return jsonify({'error': 'Document comparison failed'}), 500

@app.route('/download-revision', methods=['POST'])
def download_revision():
    try:
        data = request.get_json()
        final_text = data.get('final_text', '')
        title = data.get('title', 'Revised Essay')
        
        if not final_text:
            return jsonify({'error': 'No final text provided'}), 400
        
        # Create a new document
        doc = Document()
        
        # Add title
        title_para = doc.add_heading(title, 0)
        
        # Add the final content
        paragraphs = final_text.split('\n\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                doc.add_paragraph(paragraph.strip())
        
        # Save to memory
        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)
        
        return send_file(
            doc_io,
            as_attachment=True,
            download_name=f"{title.replace(' ', '_')}_final.docx",
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
    except Exception as e:
        print(f"Error creating download: {e}")
        return jsonify({'error': 'Failed to create download'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'ai_available': model is not None,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("Starting Essay Analyzer Server...")
    print("AI Analysis:", "Enabled" if model else "Disabled (check GEMINI_API_KEY)")
    print("Server will be available at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
