# Document Summarizer

Document Summarizer is a web application that extracts text from documents (currently supporting PDF files), analyzes the content, and generates summaries using AI. The application offers multiple summarization styles and export options.

## Features

- **Document Upload & Processing**: Upload and process PDF documents
- **Text Analysis**: Get word count, sentence count, and word frequency analysis
- **Multiple Summary Styles**: Choose from Concise, Detailed, Bullet Points, Academic, and ELI5 (Explain Like I'm 5)
- **Smart Chunking**: Handles large documents by breaking them into manageable chunks
- **Combined Summary**: Merges individual chunk summaries into one cohesive summary
- **Export Options**: Export summaries in plain text, Markdown, and JSON formats
- **Model Selection**: Choose from different AI models for summarization

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: React.js
- **Document Processing**: PyMuPDF
- **AI Models**: Hugging Face Transformers

## Installation

### Prerequisites

- Python 3.7+
- Node.js 14+
- npm or yarn

### Backend Setup

1. Clone the repository
2. Navigate to the backend directory
3. Create a virtual environment (recommended)
4. Install the required packages:

```bash
pip install flask flask-cors PyMuPDF transformers torch uuid
```

5. Create an uploads directory:

```bash
mkdir -p uploads
```

6. Start the Flask server:

```bash
python app.py
```

The backend API will be available at http://localhost:5050

### Frontend Setup

1. Navigate to the project's frontend directory
2. Install dependencies:

```bash
npm install
```

3. Start the development server:

```bash
npm start
```

The application will be available at http://localhost:3000

## API Endpoints

- `GET /` - Server status check
- `POST /process-pdf` - Process PDF documents
- `POST /summarize` - Summarize text directly
- `POST /export` - Export summaries in different formats
- `GET /available-models` - Get list of available AI models
- `GET /summary-styles` - Get list of available summary styles

## Usage

1. Open the application in your web browser
2. Upload a PDF document
3. Select your preferred summarization style and model
4. View the analysis and summary results
5. Export the summary in your preferred format

## Extending the Application

- Add support for more document types (DOCX, TXT, etc.)
- Implement additional summarization styles
- Add user authentication and saved summaries
- Integrate with cloud storage services

## License

[MIT License](LICENSE)