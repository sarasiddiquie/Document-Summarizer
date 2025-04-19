from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import fitz  # PyMuPDF
from transformers import pipeline
import os
import tempfile
import re
import base64
import json
import uuid
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('document_summarizer')

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize model cache
model_cache = {}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_model(model_name="MBZUAI/lamini-flan-t5-248m"):
    """
    Load and cache the summarization model.
    """
    if model_name not in model_cache:
        logger.info(f"Loading model: {model_name}")
        model_cache[model_name] = pipeline("text2text-generation", model=model_name)
    return model_cache[model_name]

def extract_text_from_pdf(file_path):
    """
    Extracts all text from a PDF file using PyMuPDF.
    Returns text, page count, and table of contents.
    """
    text = ""
    page_count = 0
    toc = []
    
    try:
        with fitz.open(file_path) as doc:
            page_count = len(doc)
            toc = doc.get_toc()
            
            for page in doc:
                text += page.get_text()
        
        return text, page_count, toc
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise

def analyze_text(text):
    """
    Analyze the extracted text to get basic metrics.
    """
    word_count = len(text.split())
    char_count = len(text)
    sentences = re.split(r'[.!?]+', text)
    sentence_count = len([s for s in sentences if s.strip()])
    
    avg_words_per_sentence = round(word_count / max(1, sentence_count), 1)
    
    # Word frequency analysis (top 20)
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    word_freq = {}
    for word in words:
        if word in word_freq:
            word_freq[word] += 1
        else:
            word_freq[word] = 1
    
    # Sort by frequency and get top 20
    word_freq = dict(sorted(word_freq.items(), key=lambda item: item[1], reverse=True)[:20])
    
    return {
        "word_count": word_count,
        "char_count": char_count,
        "sentence_count": sentence_count,
        "avg_words_per_sentence": avg_words_per_sentence,
        "word_freq": word_freq
    }

def chunk_text(text, max_tokens=700):
    """
    Splits the text into smaller chunks for large document summarization.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_tokens:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def get_prompt_prefix(style):
    """
    Returns the appropriate prompt prefix based on summary style.
    """
    styles = {
        "Concise": "Provide a concise and brief summary of the following text: ",
        "Detailed": "Provide a comprehensive and detailed summary of the following text, including key points and main ideas: ",
        "Bullet Points": "Summarize the following text as a list of bullet points covering the main ideas: ",
        "Academic": "Create an academic summary of the following text, highlighting methodology, findings, and conclusions: ",
        "ELI5": "Explain the following text as if explaining to a 5-year old in simple terms: "
    }
    
    return styles.get(style, style)  # Return the style itself if custom or not found

def summarize_long_text(text, model, style="Concise", max_tokens=700, min_length=100, max_length=350):
    """
    Handles long text summarization using chunking.
    """
    chunks = chunk_text(text, max_tokens)
    summaries = []
    prompt_prefix = get_prompt_prefix(style)
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Summarizing chunk {i+1}/{len(chunks)}")
        # Add prompt prefix to the chunk
        input_text = prompt_prefix + chunk
        
        # Generate summary
        try:
            result = model(
                input_text, 
                max_length=max_length, 
                min_length=min_length, 
                truncation=True, 
                do_sample=False
            )[0]['generated_text']
            
            summaries.append(result)
        except Exception as e:
            logger.error(f"Error generating summary for chunk {i+1}: {str(e)}")
            summaries.append(f"Summary generation failed for this section: {str(e)}")
    
    return summaries

def get_combined_summary(summaries, style="Concise"):
    """
    Combines multiple summary parts into a single cohesive summary
    """
    if style == "Bullet Points":
        combined = []
        for part in summaries:
            # Extract bullet points if they exist
            bullets = re.findall(r'•\s*(.*?)(?=•|\Z)', part, re.DOTALL)
            if not bullets:
                # If no bullet format detected, create bullets from sentences
                sentences = re.split(r'(?<=[.!?])\s+', part)
                bullets = [s.strip() for s in sentences if s.strip()]
            combined.extend(bullets)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_bullets = []
        for bullet in combined:
            cleaned = bullet.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                unique_bullets.append(f"• {cleaned}")
        
        return "\n".join(unique_bullets)
    else:
        # For other styles, just join with paragraph breaks
        return "\n\n".join(summaries)

# Test route to check server status
@app.route('/', methods=['GET'])
def home():
    return "✅ Document Summarizer API is running.", 200

# Static files for frontend 
@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('public', path)

# POST route to process PDF
@app.route('/process-pdf', methods=['POST'])
def process_pdf():
    start_time = time.time()
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': f'File type not supported. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    # Get parameters from the request
    model_name = request.form.get('model', 'MBZUAI/lamini-flan-t5-248m')
    summary_style = request.form.get('style', 'Concise')
    max_token_length = int(request.form.get('max_tokens', 700))
    min_summary_length = int(request.form.get('min_length', 100))
    max_summary_length = int(request.form.get('max_length', 350))
    
    try:
        # Generate unique filename to avoid collisions
        unique_filename = str(uuid.uuid4()) + "_" + file.filename
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save uploaded file
        file.save(file_path)
        logger.info(f"File saved: {file_path}")
        
        # Step 1: Extract text from PDF
        pdf_text, page_count, toc = extract_text_from_pdf(file_path)
        
        if not pdf_text.strip():
            os.remove(file_path)
            return jsonify({'error': 'No text could be extracted from the document'}), 400
        
        # Step 2: Analyze text
        analysis_results = analyze_text(pdf_text)
        
        # Step 3: Generate summary
        model = get_model(model_name)
        summary_parts = summarize_long_text(
            pdf_text,
            model,
            summary_style,
            max_tokens=max_token_length,
            min_length=min_summary_length,
            max_length=max_summary_length
        )
        
        # Get combined summary as well
        combined_summary = get_combined_summary(summary_parts, summary_style)
        
        # Calculate processing time
        processing_time = round(time.time() - start_time, 2)
        
        # Return the results
        response = {
            'filename': file.filename,
            'page_count': page_count,
            'toc': toc,
            'text_preview': pdf_text[:500] + "..." if len(pdf_text) > 500 else pdf_text,
            'analysis': analysis_results,
            'summary_parts': summary_parts,
            'combined_summary': combined_summary,
            'processing_time': processing_time,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Store the file_path in a session or database if you want to keep it
        # For this example, we'll clean up the file:
        os.remove(file_path)
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        # Clean up if there was an error
        try:
            os.remove(file_path)
        except:
            pass
        return jsonify({'error': f"Processing failed: {str(e)}"}), 500

# POST route to summarize text only
@app.route('/summarize', methods=['POST'])
def summarize():
    if not request.is_json:
        return jsonify({'error': 'Request must be in JSON format'}), 400
    
    data = request.get_json()
    text = data.get('text', '')
    
    if not text.strip():
        return jsonify({'error': 'No text provided'}), 400
    
    # Get parameters from the request
    model_name = data.get('model', 'MBZUAI/lamini-flan-t5-248m')
    summary_style = data.get('style', 'Concise')
    max_token_length = data.get('max_tokens', 700)
    min_summary_length = data.get('min_length', 100)
    max_summary_length = data.get('max_length', 350)
    
    try:
        start_time = time.time()
        
        model = get_model(model_name)
        summary_parts = summarize_long_text(
            text,
            model,
            summary_style,
            max_tokens=max_token_length,
            min_length=min_summary_length,
            max_length=max_summary_length
        )
        
        # Get combined summary
        combined_summary = get_combined_summary(summary_parts, summary_style)
        
        # Analyze text as well for completeness
        analysis_results = analyze_text(text)
        
        processing_time = round(time.time() - start_time, 2)
        
        return jsonify({
            'analysis': analysis_results,
            'summary_parts': summary_parts,
            'combined_summary': combined_summary,
            'processing_time': processing_time,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        logger.error(f"Summarization failed: {str(e)}")
        return jsonify({'error': f"Summarization failed: {str(e)}"}), 500

# Route to export summary in different formats
@app.route('/export', methods=['POST'])
def export_summary():
    if not request.is_json:
        return jsonify({'error': 'Request must be in JSON format'}), 400
    
    data = request.get_json()
    export_format = data.get('format', 'text')
    filename = data.get('filename', 'document')
    summary_parts = data.get('summary_parts', [])
    combined_summary = data.get('combined_summary', '')
    meta = data.get('meta', {})
    
    try:
        if export_format == 'text':
            content = f"SUMMARY OF: {filename}\n"
            content += f"Generated on: {meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}\n"
            content += f"Document stats: {meta.get('page_count', 'N/A')} pages, {meta.get('word_count', 'N/A')} words\n\n"
            content += "SUMMARY:\n\n"
            
            if combined_summary:
                content += combined_summary
            else:
                for i, part in enumerate(summary_parts):
                    content += f"--- Part {i+1} ---\n{part}\n\n"
            
            response = {
                'content': base64.b64encode(content.encode()).decode(),
                'filename': f"{os.path.splitext(filename)[0]}_summary.txt"
            }
            
        elif export_format == 'markdown':
            content = f"# Summary of {filename}\n\n"
            content += f"*Generated on: {meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}*\n\n"
            content += f"**Document statistics:**\n- Pages: {meta.get('page_count', 'N/A')}\n"
            content += f"- Words: {meta.get('word_count', 'N/A')}\n"
            content += f"- Sentences: {meta.get('sentence_count', 'N/A')}\n\n"
            content += "## Summary Content\n\n"
            
            if combined_summary:
                content += combined_summary
            else:
                for i, part in enumerate(summary_parts):
                    content += f"### Part {i+1}\n\n{part}\n\n"
            
            response = {
                'content': base64.b64encode(content.encode()).decode(),
                'filename': f"{os.path.splitext(filename)[0]}_summary.md"
            }
            
        elif export_format == 'json':
            export_data = {
                "document": {
                    "filename": filename,
                    "pages": meta.get('page_count', 'N/A'),
                    "generated_date": meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                },
                "analysis": {
                    "word_count": meta.get('word_count', 'N/A'),
                    "sentence_count": meta.get('sentence_count', 'N/A'),
                    "avg_words_per_sentence": meta.get('avg_words_per_sentence', 'N/A')
                },
                "summary_parts": summary_parts,
                "combined_summary": combined_summary
            }
            
            json_str = json.dumps(export_data, indent=2)
            
            response = {
                'content': base64.b64encode(json_str.encode()).decode(),
                'filename': f"{os.path.splitext(filename)[0]}_summary.json"
            }
            
        else:
            return jsonify({'error': 'Unsupported export format'}), 400
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Export failed: {str(e)}")
        return jsonify({'error': f"Export failed: {str(e)}"}), 500

# Get list of available models
@app.route('/available-models', methods=['GET'])
def get_available_models():
    # You can expand this list as needed
    available_models = [
        {
            "id": "MBZUAI/lamini-flan-t5-248m",
            "name": "Lamini Flan T5 Small",
            "description": "Fast and efficient summarization model",
            "size": "248M parameters"
        },
        {
            "id": "facebook/bart-large-cnn",
            "name": "BART CNN",
            "description": "Optimized for news summarization",
            "size": "400M parameters"
        },
        {
            "id": "google/pegasus-xsum",
            "name": "Pegasus XSum",
            "description": "Extreme summarization model",
            "size": "568M parameters"
        }
    ]
    
    return jsonify(available_models)

# Get available summary styles
@app.route('/summary-styles', methods=['GET'])
def get_summary_styles():
    styles = [
        {
            "id": "Concise",
            "name": "Concise",
            "description": "Brief summary highlighting key points"
        },
        {
            "id": "Detailed",
            "name": "Detailed",
            "description": "Comprehensive summary with more information"
        },
        {
            "id": "Bullet Points",
            "name": "Bullet Points",
            "description": "Summary formatted as bullet points"
        },
        {
            "id": "Academic",
            "name": "Academic",
            "description": "Formal summary suitable for academic context"
        },
        {
            "id": "ELI5",
            "name": "Explain Like I'm 5",
            "description": "Simple summary in easy-to-understand language"
        }
    ]
    
    return jsonify(styles)

if __name__ == '__main__':
    logger.info("Starting Document Summarizer API")
    app.run(debug=True, host="0.0.0.0", port=5050)