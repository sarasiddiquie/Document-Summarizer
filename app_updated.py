import streamlit as st
import fitz  # PyMuPDF
from transformers import pipeline

# Set page config must be the first Streamlit command
st.set_page_config(page_title="PDF Summarizer", page_icon="📄", layout="centered")

# Load the model only once
@st.cache_resource
def load_model():
    return pipeline("text2text-generation", model="MBZUAI/lamini-flan-t5-248m")

model = load_model()

def extract_text_from_pdf(uploaded_file):
    """
    Extracts all text from a PDF file using PyMuPDF.
    """
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def chunk_text(text, max_tokens=700):
    """
    Splits the text into smaller chunks for large document summarization.
    """
    sentences = text.split('. ')
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_tokens:
            current_chunk += sentence + ". "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

def summarize_long_text(text):
    """
    Handles long text summarization using chunking.
    """
    chunks = chunk_text(text)
    full_summary = ""

    for i, chunk in enumerate(chunks):
        with st.spinner(f"Summarizing part {i + 1} of {len(chunks)}..."):
            result = model(chunk, max_length=350, min_length=100, truncation=True, do_sample=False)[0]['generated_text']
            full_summary += f"### 📌 Part {i + 1}:\n{result}\n\n"

    return full_summary.strip()

# Streamlit UI
st.title("📄 PDF Summarizer using LaMini-Flan-T5")

uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

if uploaded_file:
    st.info("⏳ Extracting text from the uploaded PDF...")
    pdf_text = extract_text_from_pdf(uploaded_file)

    if pdf_text.strip():
        st.success("✅ Text extracted! Generating summary...")
        summary = summarize_long_text(pdf_text)
        st.markdown("---")
        st.subheader("📝 Final Summary")
        st.markdown(summary)
    else:
        st.error("⚠️ No text could be extracted from the PDF.")