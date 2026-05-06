import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, Search, Sparkles, Upload } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="view active">
      <div className="view-header">
        <h1 className="view-title">Welcome to BugHunter</h1>
        <p className="view-subtitle">CS 810 Final Project: Static Analysis with AI Triage</p>
      </div>

      <div className="card">
        <h2 className="card-title" style={{ fontSize: '1.4rem', color: 'var(--feather-green)' }}>What is this?</h2>
        <p style={{ lineHeight: 1.6, marginBottom: '20px' }}>
          BugHunter is an automated workflow that analyzes your C code using two industry-standard tools: 
          <strong> Cppcheck</strong> and <strong>Clang Static Analyzer</strong>. 
          When both tools flag the same issue, it's considered a <strong>Critical Candidate</strong>.
        </p>
        <p style={{ lineHeight: 1.6 }}>
          We then use <strong>Google's Gemini AI</strong> to analyze these critical bugs, providing a confidence score, plain-english explanation, and a suggested fix.
        </p>
      </div>

      <h2 style={{ marginTop: '30px', marginBottom: '15px' }}>How to Use</h2>
      <div className="stat-grid" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ opacity: 1, color: 'var(--dodger-blue)' }}><Upload size={32} /></div>
          <h3 style={{ marginTop: '10px', fontSize: '1.2rem' }}>1. Upload</h3>
          <p style={{ marginTop: '10px', color: 'var(--wolf)', fontSize: '0.9rem' }}>Upload your .c and .h files directly from your computer.</p>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ opacity: 1, color: 'var(--fox-orange)' }}><Search size={32} /></div>
          <h3 style={{ marginTop: '10px', fontSize: '1.2rem' }}>2. Analyze</h3>
          <p style={{ marginTop: '10px', color: 'var(--wolf)', fontSize: '0.9rem' }}>We run Cppcheck and Clang in the background to find bugs.</p>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ opacity: 1, color: 'var(--beetle-purple)' }}><Sparkles size={32} /></div>
          <h3 style={{ marginTop: '10px', fontSize: '1.2rem' }}>3. Review</h3>
          <p style={{ marginTop: '10px', color: 'var(--wolf)', fontSize: '0.9rem' }}>View the gamified dashboard and Gemini AI recommendations.</p>
        </div>
      </div>

      <div style={{ marginTop: '30px', textAlign: 'center' }}>
        <Link to="/upload" className="nav-btn active" style={{ display: 'inline-flex', padding: '15px 30px', fontSize: '1.1rem', justifyContent: 'center', width: 'auto' }}>
          Start Analyzing Now
        </Link>
      </div>
    </div>
  );
}
