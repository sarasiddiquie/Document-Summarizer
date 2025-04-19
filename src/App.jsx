// src/App.jsx
import { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState({
    status: '',
    current: 0,
    total: 0
  });
  const [summaryStyles, setSummaryStyles] = useState([]);
  const [selectedStyle, setSelectedStyle] = useState('Concise');

  // Fetch available summary styles when component mounts
  useEffect(() => {
    const fetchSummaryStyles = async () => {
      try {
        const response = await fetch('http://localhost:5050/summary-styles');
        if (response.ok) {
          const styles = await response.json();
          setSummaryStyles(styles);
        }
      } catch (err) {
        console.error('Error fetching summary styles:', err);
      }
    };

    fetchSummaryStyles();
  }, []);

  const handleFileUpload = async (selectedFile) => {
    if (!selectedFile) return;
    
    setFile(selectedFile);
    setLoading(true);
    setError(null);
    setSummary(null);
    setProgress({ status: 'Processing document...', current: 0, total: 3 });

    try {
      // Create FormData to send file to backend
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('style', selectedStyle);

      // Process PDF in one API call
      const response = await fetch('http://localhost:5050/process-pdf', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to process PDF');
      }

      setProgress({ status: 'Analyzing document...', current: 1, total: 3 });
      
      // Since our backend now processes everything in one go, we just need to wait for the response
      setTimeout(() => {
        setProgress({ status: 'Generating summary...', current: 2, total: 3 });
      }, 1000);

      const result = await response.json();
      
      setSummary({
        filename: selectedFile.name,
        pages: result.page_count,
        summaryParts: result.summary_parts,
        combinedSummary: result.combined_summary,
        analysis: result.analysis,
        processingTime: result.processing_time
      });
      
      setProgress({ status: 'Complete', current: 3, total: 3 });
    } catch (err) {
      console.error('Error processing PDF:', err);
      setError(err.message || 'Error processing PDF');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setSummary(null);
    setError(null);
  };

  const handleExport = async (format) => {
    if (!summary) return;

    try {
      const response = await fetch('http://localhost:5050/export', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          format: format,
          filename: summary.filename,
          summary_parts: summary.summaryParts,
          combined_summary: summary.combinedSummary,
          meta: {
            date: new Date().toISOString(),
            page_count: summary.pages,
            word_count: summary.analysis.word_count,
            sentence_count: summary.analysis.sentence_count,
            avg_words_per_sentence: summary.analysis.avg_words_per_sentence
          }
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to export summary');
      }

      const result = await response.json();
      
      // Create blob from base64 content
      const content = atob(result.content);
      const blob = new Blob([content], { type: getContentType(format) });
      
      // Create download link
      const downloadLink = document.createElement('a');
      downloadLink.href = URL.createObjectURL(blob);
      downloadLink.download = result.filename;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      
    } catch (err) {
      console.error('Error exporting summary:', err);
      setError(err.message || 'Error exporting summary');
    }
  };

  const getContentType = (format) => {
    switch (format) {
      case 'markdown':
        return 'text/markdown';
      case 'json':
        return 'application/json';
      default:
        return 'text/plain';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-blue-600 text-white shadow-lg">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center">
            <span className="text-3xl mr-3">📄</span>
            <div>
              <h1 className="text-2xl font-bold">Document Summarizer</h1>
              <p className="text-blue-100">Powered by LaMini-Flan-T5</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Upload Section */}
        {!summary && !loading && (
          <div className="mt-8">
            <div className="max-w-xl mx-auto">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (file) handleFileUpload(file);
                }}
                className="flex flex-col items-center"
              >
                <div 
                  className="w-full p-8 border-2 border-dashed rounded-lg flex flex-col items-center justify-center cursor-pointer transition-colors border-gray-300 bg-white hover:bg-gray-50"
                  onClick={() => document.getElementById('file-input').click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                      const droppedFile = e.dataTransfer.files[0];
                      if (droppedFile.type === 'application/pdf') {
                        setFile(droppedFile);
                      }
                    }
                  }}
                >
                  <input
                    id="file-input"
                    type="file"
                    className="hidden"
                    accept=".pdf"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setFile(e.target.files[0]);
                      }
                    }}
                  />
                  
                  <div className="text-6xl mb-4">📄</div>
                  <h3 className="text-lg font-medium text-gray-700">Upload your document</h3>
                  <p className="mt-1 text-sm text-gray-500">
                    {file ? file.name : "Drag and drop or click to browse"}
                  </p>
                  
                  {file && (
                    <span className="mt-3 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </span>
                  )}
                </div>
                
                {/* Summary Style Selection */}
                <div className="w-full mt-6">
                  <label className="block text-sm font-medium text-gray-700 mb-1">Summary Style</label>
                  <select
                    value={selectedStyle}
                    onChange={(e) => setSelectedStyle(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {summaryStyles.length > 0 ? (
                      summaryStyles.map((style) => (
                        <option key={style.id} value={style.id}>
                          {style.name} - {style.description}
                        </option>
                      ))
                    ) : (
                      <option value="Concise">Concise - Brief summary highlighting key points</option>
                    )}
                  </select>
                </div>
                
                <button
                  type="submit"
                  disabled={!file}
                  className={`mt-6 px-6 py-3 rounded-md font-medium text-white shadow-md transition-all
                    ${file 
                      ? 'bg-blue-600 hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2' 
                      : 'bg-gray-400 cursor-not-allowed'}`}
                >
                  {file ? 'Generate Summary' : 'Select a PDF File'}
                </button>
              </form>
            </div>
          </div>
        )}
        
        {/* Loading Indicator */}
        {loading && (
          <div className="mt-12 max-w-xl mx-auto p-6 bg-white rounded-lg shadow">
            <h3 className="text-xl font-semibold text-gray-800">Processing your document</h3>
            
            <div className="mt-6">
              <div className="flex justify-between mb-2">
                <span className="text-sm font-medium text-blue-700">{progress.status}</span>
                <span className="text-sm font-medium text-blue-700">
                  {Math.round((progress.current / progress.total) * 100)}%
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2.5">
                <div 
                  className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${Math.round((progress.current / progress.total) * 100)}%` }}
                ></div>
              </div>
            </div>
            
            <div className="mt-6 flex items-center justify-center">
              <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <p className="ml-3 text-gray-600">This may take a minute for large documents...</p>
            </div>
          </div>
        )}
        
        {/* Error Message */}
        {error && (
          <div className="mt-8 p-6 bg-red-50 rounded-lg border border-red-200 max-w-xl mx-auto">
            <h3 className="text-lg font-medium text-red-800">Error</h3>
            <p className="mt-2 text-red-700">{error}</p>
            <button 
              onClick={handleReset}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500"
            >
              Try Again
            </button>
          </div>
        )}
        
        {/* Summary Section */}
        {summary && (
          <div className="mt-8">
            <div className="bg-white rounded-lg shadow-lg overflow-hidden">
              <div className="p-6 bg-blue-600 text-white">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-xl font-bold">{summary.filename}</h2>
                    <p className="text-blue-100">
                      {summary.pages} pages • {summary.analysis.word_count} words • 
                      Processed in {summary.processingTime}s
                    </p>
                  </div>
                  <div className="flex space-x-2">
                    <div className="dropdown inline-block relative">
                      <button className="px-4 py-2 bg-blue-700 text-white rounded-md hover:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-white flex items-center">
                        <span>Export</span>
                        <svg className="ml-1 w-4 h-4 fill-current" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                          <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"/>
                        </svg>
                      </button>
                      <div className="dropdown-menu absolute hidden text-gray-700 pt-1 right-0 w-32 z-10">
                        <button 
                          onClick={() => handleExport('text')}
                          className="w-full bg-white hover:bg-gray-100 py-2 px-4 block text-left text-sm"
                        >
                          Plain Text
                        </button>
                        <button 
                          onClick={() => handleExport('markdown')}
                          className="w-full bg-white hover:bg-gray-100 py-2 px-4 block text-left text-sm"
                        >
                          Markdown
                        </button>
                        <button 
                          onClick={() => handleExport('json')}
                          className="w-full bg-white hover:bg-gray-100 py-2 px-4 block text-left text-sm"
                        >
                          JSON
                        </button>
                      </div>
                    </div>
                    
                    <button
                      onClick={handleReset}
                      className="px-4 py-2 bg-white text-blue-700 rounded-md hover:bg-blue-50 focus:outline-none focus:ring-2 focus:ring-white"
                    >
                      New Document
                    </button>
                  </div>
                </div>
              </div>
              
              {/* Document Analysis */}
              <div className="p-6 border-b">
                <h3 className="text-lg font-bold text-gray-800 mb-4">Document Analysis</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <p className="text-sm text-blue-600">Word Count</p>
                    <p className="text-2xl font-bold text-blue-800">{summary.analysis.word_count}</p>
                  </div>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <p className="text-sm text-green-600">Sentences</p>
                    <p className="text-2xl font-bold text-green-800">{summary.analysis.sentence_count}</p>
                  </div>
                  <div className="bg-purple-50 p-4 rounded-lg">
                    <p className="text-sm text-purple-600">Avg Words/Sentence</p>
                    <p className="text-2xl font-bold text-purple-800">{summary.analysis.avg_words_per_sentence}</p>
                  </div>
                  <div className="bg-yellow-50 p-4 rounded-lg">
                    <p className="text-sm text-yellow-600">Pages</p>
                    <p className="text-2xl font-bold text-yellow-800">{summary.pages}</p>
                  </div>
                </div>
                
                {/* Word Frequency */}
                {summary.analysis.word_freq && Object.keys(summary.analysis.word_freq).length > 0 && (
                  <div className="mt-6">
                    <h4 className="font-medium text-gray-700 mb-2">Top Words</h4>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(summary.analysis.word_freq).slice(0, 10).map(([word, count]) => (
                        <span key={word} className="px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">
                          {word} ({count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              
              {/* Combined Summary */}
              <div className="p-6 border-b">
                <h3 className="text-xl font-bold text-gray-800 mb-4">Summary</h3>
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                  <p className="text-gray-700 whitespace-pre-line">{summary.combinedSummary}</p>
                </div>
              </div>
              
              {/* Individual Summary Parts */}
              <div className="p-6">
                <h3 className="text-xl font-bold text-gray-800 mb-4">Detailed Sections</h3>
                
                {summary.summaryParts.map((part, index) => (
                  <div key={index} className="mb-6 last:mb-0">
                    <h4 className="text-md font-semibold text-blue-700 mb-2">
                      Part {index + 1}
                    </h4>
                    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                      <p className="text-gray-700 whitespace-pre-line">{part}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
      
      {/* Add some CSS for the dropdown */}
      <style jsx="true">{`
        .dropdown:hover .dropdown-menu {
          display: block;
        }
      `}</style>
    </div>
  );
}

export default App;