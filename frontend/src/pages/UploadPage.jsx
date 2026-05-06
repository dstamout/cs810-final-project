import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { UploadCloud, CheckCircle, Loader2 } from 'lucide-react';

export default function UploadPage() {
  const [files, setFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [useGemini, setUseGemini] = useState(true);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleFileChange = (e) => {
    const validExts = ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp'];
    setFiles(Array.from(e.target.files).filter(f => validExts.some(ext => f.name.toLowerCase().endsWith(ext))));
    setError('');
  };

  const handleUploadAndAnalyze = async () => {
    if (files.length === 0) {
      setError('Please select at least one C or C++ source file.');
      return;
    }

    try {
      setIsUploading(true);
      setError('');
      
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      
      const uploadRes = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      setIsUploading(false);
      setIsAnalyzing(true);
      
      const analyzeRes = await axios.post('/api/analyze', {
        session_id: uploadRes.data.session_id,
        use_gemini: useGemini
      });
      
      if (analyzeRes.data.error) {
        throw new Error(analyzeRes.data.error);
      }
      
      // Navigate to dashboard and pass the report name
      navigate('/dashboard', { state: { reportName: analyzeRes.data.report } });
      
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'An error occurred during analysis.');
      setIsUploading(false);
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="view active">
      <div className="view-header">
        <h1 className="view-title">Upload Source Code</h1>
        <p className="view-subtitle">Select C/C++ files to analyze</p>
      </div>

      <div className="card" style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'center' }}>
        
        <div style={{ border: '3px dashed var(--swan)', borderRadius: 'var(--radius)', padding: '40px 20px', cursor: 'pointer', background: 'var(--polar)', marginBottom: '20px', position: 'relative' }}>
          <input 
            type="file" 
            multiple 
            accept=".c,.cpp,.cc,.cxx,.h,.hpp"
            onChange={handleFileChange}
            style={{ position: 'absolute', inset: 0, opacity: 0, cursor: 'pointer' }}
          />
          <UploadCloud size={48} color="var(--dodger-blue)" style={{ margin: '0 auto 15px' }} />
          <h3 style={{ marginBottom: '10px' }}>Drag & Drop or Click to Select</h3>
          <p style={{ color: 'var(--wolf)', fontSize: '0.9rem' }}>Supports C/C++ files (.c, .cpp, .h, etc)</p>
        </div>

        {files.length > 0 && (
          <div style={{ textAlign: 'left', marginBottom: '20px', background: 'var(--surface)', padding: '15px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <h4 style={{ marginBottom: '10px' }}>Selected Files ({files.length}):</h4>
            <ul style={{ listStyle: 'none', padding: 0, maxHeight: '150px', overflowY: 'auto' }}>
              {files.map((f, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', marginBottom: '5px' }}>
                  <CheckCircle size={16} color="var(--feather-green)" /> {f.name}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px', marginBottom: '25px' }}>
          <input 
            type="checkbox" 
            id="use-gemini" 
            checked={useGemini}
            onChange={(e) => setUseGemini(e.target.checked)}
            style={{ width: '18px', height: '18px' }}
          />
          <label htmlFor="use-gemini" style={{ fontWeight: 'bold' }}>Enable Gemini AI Triage ✨</label>
        </div>

        {error && <div className="gemini-error" style={{ marginBottom: '20px', textAlign: 'left' }}>{error}</div>}

        {isAnalyzing && (
          <div style={{ marginBottom: '20px', color: 'var(--dodger-blue)', fontWeight: 'bold' }}>
            <Loader2 className="animate-spin" style={{ display: 'inline-block', marginRight: '8px' }} />
            {useGemini ? "Analyzing... Please wait ~15-30 seconds for AI processing" : "Running static analysis... Please wait ~5-10 seconds"}
          </div>
        )}

        <button 
          className="nav-btn active" 
          onClick={handleUploadAndAnalyze}
          disabled={isUploading || isAnalyzing || files.length === 0}
          style={{ justifyContent: 'center', padding: '15px', fontSize: '1.1rem', opacity: (isUploading || isAnalyzing || files.length === 0) ? 0.7 : 1 }}
        >
          {isUploading ? <><Loader2 className="animate-spin" /> Uploading...</> : 
           isAnalyzing ? 'Processing...' : 
           'Run Analysis'}
        </button>
      </div>
    </div>
  );
}
