# Document Text Analyzer

This Python script extracts text from various document formats (DOC, DOCX, PDF, PPTX) and analyzes it using Google's Gemini AI for grammar mistakes, sentence corrections, and more.

## Features

- Extracts text from multiple document formats:
  - DOCX files (using python-docx and docx2txt)
  - DOC files (using docx2txt with fallback options)
  - PDF files (using PyPDF2, if installed)
  - PPTX files (using python-pptx, if installed)
- Analyzes text using Google's Gemini AI (gemini-2.0-flash model by default)
- Identifies grammar mistakes and suggests corrections
- Tags words that should be added with [ADD: word]
- Tags words that should be deleted with [DELETE: word]
- Tags words that should be replaced with [REPLACE: original_word -> new_word]
- Saves both original and analyzed text to a file
- Supports configuration via .env file

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file in the project directory with your Google API key:

```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

You can get a Google API key for Gemini AI from the Google AI Studio (https://makersuite.google.com/)

## Usage

Run the script with the following command:

```bash
python doc_analyzer.py path/to/your/document.docx
```

### Arguments

- `file_path`: Path to the document file (required)
- `--api_key`: Google API key for Gemini AI (optional, overrides .env setting)
- `--output`: Output file path (default: analysis_results.txt)
- `--model`: Gemini AI model to use (optional, overrides .env setting)

## Examples

Basic usage (using API key from .env file):

```bash
python doc_analyzer.py my_document.docx
```

Specifying API key via command line:

```bash
python doc_analyzer.py my_document.docx --api_key YOUR_API_KEY
```

Specifying output file and model:

```bash
python doc_analyzer.py my_document.docx --output my_analysis.txt --model gemini-1.5-pro
```

## Requirements

- Python 3.7+
- python-docx: For DOCX file processing
- docx2txt: Alternative for DOC/DOCX processing
- PyPDF2 (optional): For PDF file processing
- python-pptx (optional): For PowerPoint file processing
- google-generativeai: For accessing Gemini AI
- python-dotenv: For loading environment variables from .env file
