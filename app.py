import os
import re
import json
from flask import Flask, render_template, request, jsonify
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
    raise ValueError("GEMINI_API_KEY not found in environment variables. Please add it to your .env file.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

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

class DocumentComparator:
    def __init__(self):
        self.model = model
    
    def compare_documents(self, doc1_content, doc2_content, doc1_name="Document 1", doc2_name="Document 2"):
        """Compare two documents line by line and provide detailed analysis"""
        
        # Split documents into lines for comparison
        lines1 = doc1_content['text'].split('\n')
        lines2 = doc2_content['text'].split('\n')
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            lines1, lines2,
            fromfile=doc1_name,
            tofile=doc2_name,
            lineterm=''
        ))
        
        # Create detailed comparison
        comparison_data = self._create_detailed_comparison(lines1, lines2)
        
        # AI analysis of changes
        ai_analysis = self._analyze_changes_with_ai(doc1_content['text'], doc2_content['text'], comparison_data)
        
        return {
            'diff': diff,
            'comparison_data': comparison_data,
            'ai_analysis': ai_analysis,
            'statistics': {
                'doc1_lines': len(lines1),
                'doc2_lines': len(lines2),
                'doc1_words': len(doc1_content['text'].split()),
                'doc2_words': len(doc2_content['text'].split()),
                'doc1_paragraphs': doc1_content['paragraph_count'],
                'doc2_paragraphs': doc2_content['paragraph_count']
            }
        }
    
    def _create_detailed_comparison(self, lines1, lines2):
        """Create detailed line-by-line comparison"""
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        comparison = []
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                for i in range(i1, i2):
                    comparison.append({
                        'type': 'equal',
                        'line_num1': i + 1,
                        'line_num2': j1 + (i - i1) + 1,
                        'content1': lines1[i],
                        'content2': lines2[j1 + (i - i1)] if j1 + (i - i1) < len(lines2) else ''
                    })
            elif tag == 'delete':
                for i in range(i1, i2):
                    comparison.append({
                        'type': 'delete',
                        'line_num1': i + 1,
                        'line_num2': None,
                        'content1': lines1[i],
                        'content2': ''
                    })
            elif tag == 'insert':
                for j in range(j1, j2):
                    comparison.append({
                        'type': 'insert',
                        'line_num1': None,
                        'line_num2': j + 1,
                        'content1': '',
                        'content2': lines2[j]
                    })
            elif tag == 'replace':
                max_lines = max(i2 - i1, j2 - j1)
                for k in range(max_lines):
                    line1 = lines1[i1 + k] if i1 + k < i2 else ''
                    line2 = lines2[j1 + k] if j1 + k < j2 else ''
                    comparison.append({
                        'type': 'replace',
                        'line_num1': (i1 + k + 1) if i1 + k < i2 else None,
                        'line_num2': (j1 + k + 1) if j1 + k < j2 else None,
                        'content1': line1,
                        'content2': line2
                    })
        
        return comparison
    
    def _analyze_changes_with_ai(self, text1, text2, comparison_data):
        """Use AI to analyze the significance of changes between documents"""
        
        # Count different types of changes
        changes_summary = {
            'additions': len([c for c in comparison_data if c['type'] == 'insert']),
            'deletions': len([c for c in comparison_data if c['type'] == 'delete']),
            'modifications': len([c for c in comparison_data if c['type'] == 'replace'])
        }
        
        # Get sample changes for AI analysis
        sample_changes = comparison_data[:20]  # Analyze first 20 changes
        
        prompt = f"""
        Analyze the changes between two essay versions and provide insights in JSON format.
        
        Changes Summary:
        - Additions: {changes_summary['additions']} lines
        - Deletions: {changes_summary['deletions']} lines  
        - Modifications: {changes_summary['modifications']} lines
        
        Sample Changes:
        {json.dumps(sample_changes[:10], indent=2)}
        
        Original Text (first 1000 chars):
        {text1[:1000]}
        
        Revised Text (first 1000 chars):
        {text2[:1000]}
        
        Provide analysis in this JSON format:
        {{
            "overall_assessment": "brief overall assessment of changes",
            "change_categories": [
                {{"category": "Grammar", "count": 0, "impact": "low/medium/high", "examples": []}},
                {{"category": "Content", "count": 0, "impact": "low/medium/high", "examples": []}},
                {{"category": "Structure", "count": 0, "impact": "low/medium/high", "examples": []}},
                {{"category": "Style", "count": 0, "impact": "low/medium/high", "examples": []}}
            ],
            "key_improvements": ["list of key improvements made"],
            "potential_concerns": ["list of potential issues with changes"],
            "revision_quality": "poor/fair/good/excellent",
            "recommendations": ["suggestions for further improvement"]
        }}
        """
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_str = response_text[json_start:json_end]
                ai_analysis = json.loads(json_str)
                ai_analysis['changes_summary'] = changes_summary
                return ai_analysis
            else:
                return self._fallback_comparison_analysis(changes_summary)
        except Exception as e:
            print(f"Error in AI comparison analysis: {e}")
            return self._fallback_comparison_analysis(changes_summary)
    
    def _fallback_comparison_analysis(self, changes_summary):
        """Fallback analysis when AI fails"""
        return {
            "overall_assessment": "Document comparison completed with basic analysis",
            "change_categories": [
                {"category": "Grammar", "count": 0, "impact": "unknown", "examples": []},
                {"category": "Content", "count": changes_summary['additions'], "impact": "medium", "examples": []},
                {"category": "Structure", "count": changes_summary['modifications'], "impact": "medium", "examples": []},
                {"category": "Style", "count": changes_summary['deletions'], "impact": "low", "examples": []}
            ],
            "key_improvements": ["Changes detected between documents"],
            "potential_concerns": ["AI analysis unavailable - manual review recommended"],
            "revision_quality": "unknown",
            "recommendations": ["Enable AI analysis with valid API key"],
            "changes_summary": changes_summary
        }

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
        primary_type = max(scores, key=scores.get)
        
        # Check for hybrid essays (multiple high scores)
        high_scores = [t for t, s in scores.items() if s >= max(scores.values()) * 0.7]
        
        return {
            'primary_type': primary_type,
            'hybrid_types': high_scores if len(high_scores) > 1 else [],
            'confidence': scores[primary_type] / len(ESSAY_TYPES[primary_type]['keywords']) if ESSAY_TYPES[primary_type]['keywords'] else 0
        }
    
    def analyze_grammar_and_style(self, text):
        """Analyze grammar, style, and structure using Gemini AI"""
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
        {text}
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
        {text}
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
        prompt = f"""
        Analyze the following essay and provide specific word-level and sentence-level suggestions for improvement.
        For each suggestion, provide the exact original text and the suggested replacement.
        
        Provide the response in JSON format:
        {{
            "suggestions": [
                {{
                    "id": "unique_id",
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
        
        Essay text:
        {text}
        
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
                return json.loads(json_str)
            else:
                return self._fallback_suggestions(text)
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return self._fallback_suggestions(text)
    
    def _fallback_analysis(self, text):
        """Fallback analysis when AI fails"""
        return {
            "grammar_issues": [
                {"issue": "AI analysis unavailable", "suggestion": "Please check manually", "line": "N/A"}
            ],
            "style_issues": [],
            "structure_issues": [],
            "overall_score": "75",
            "strengths": ["Content provided"],
            "priority_improvements": ["Enable AI analysis with valid API key"]
        }
    
    def _fallback_type_analysis(self, essay_type):
        """Fallback type-specific analysis"""
        return {
            "criteria_analysis": [
                {"criterion": f"{essay_type} structure", "score": "7", "feedback": "AI analysis unavailable"}
            ],
            "source_issues": [],
            "type_specific_suggestions": [f"Review {essay_type} essay guidelines"]
        }
    
    def _fallback_suggestions(self, text):
        """Fallback suggestions when AI fails"""
        return {
            "suggestions": [
                {
                    "id": "fallback_1",
                    "type": "system",
                    "original": "AI suggestions unavailable",
                    "suggested": "Please check your API key configuration",
                    "reason": "AI service is not available",
                    "position": {"start": 0, "end": 0},
                    "severity": "low"
                }
            ]
        }

# Initialize analyzer
analyzer = EssayAnalyzer()
doc_processor = DocumentProcessor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_essay():
    try:
        data = request.get_json()
        essay_text = data.get('text', '')
        
        if not essay_text.strip():
            return jsonify({'error': 'No essay text provided'}), 400
        
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
        return jsonify({'error': 'Analysis failed. Please try again.'}), 500

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
