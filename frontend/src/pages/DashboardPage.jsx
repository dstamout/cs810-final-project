import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import axios from 'axios';

export default function DashboardPage() {
  const location = useLocation();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        // Get from location state, or fallback to localStorage, or default
        const stateReport = location.state?.reportName;
        const storedReport = localStorage.getItem('lastReportName');
        const reportName = stateReport || storedReport || 'gemini_report.json';
        
        // Save to localStorage so it persists when we leave the page
        localStorage.setItem('lastReportName', reportName);
        
        const res = await axios.get(`/api/report/${reportName}`);
        setReport(res.data);
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load report. Please upload and analyze code first.');
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [location.state]);

  if (loading) return <div className="view active"><div style={{padding:'40px',textAlign:'center'}}>Loading dashboard...</div></div>;
  if (error) return <div className="view active"><div className="gemini-error" style={{margin:'40px'}}>{error}</div></div>;
  if (!report) return null;

  const { meta, findings } = report;
  const allFindings = [
    ...(findings.cppcheck_only || []), 
    ...(findings.clang_only || []),
    ...(findings.critical_candidates?.map(c => c.cppcheck) || []),
    ...(findings.critical_candidates?.map(c => c.clang) || [])
  ];
  const critCount = (findings.critical_candidates || []).length;
  // Total raw findings is the length of allFindings
  const totalCount = allFindings.length;
  const errorCount = allFindings.filter(f => f.severity === 'error').length;
  const score = Math.max(0, Math.round(100 - (errorCount / Math.max(totalCount, 1)) * 100));

  const extractFilename = (path) => path ? path.replace(/\\/g, '/').split('/').pop() : 'unknown';
  
  // Use localStorage reportName if location state is missing
  const currentReportName = localStorage.getItem('lastReportName') || 'Default Report';

  return (
    <div className="view active">
      <div className="view-header">
        <h1 className="view-title">Analysis Dashboard</h1>
        <p className="view-subtitle">Report: {currentReportName}</p>
      </div>

      {/* Tabs */}
      <div className="filter-bar">
        <button className={`filter-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>Overview</button>
        <button className={`filter-btn ${activeTab === 'all' ? 'active' : ''}`} onClick={() => setActiveTab('all')}>All Bugs ({totalCount})</button>
        <button className={`filter-btn ${activeTab === 'critical' ? 'active' : ''}`} onClick={() => setActiveTab('critical')}>Critical Candidates ({critCount})</button>
        <button className={`filter-btn ${activeTab === 'triage' ? 'active' : ''}`} onClick={() => setActiveTab('triage')}>AI Triage</button>
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="xp-bar-container">
            <div className="xp-label">
              <span className="xp-level">Security Score</span>
              <span className="xp-value">{score}/100</span>
            </div>
            <div className="xp-track">
              <div className="xp-fill" style={{ width: `${score}%` }}></div>
            </div>
          </div>

          <div className="stat-grid">
            <div className="stat-card stat-card--green">
              <div className="stat-number">{meta.file_count}</div>
              <div className="stat-label">Files Scanned</div>
            </div>
            <div className="stat-card stat-card--blue">
              <div className="stat-number">{meta.cppcheck_count}</div>
              <div className="stat-label">Cppcheck Findings</div>
            </div>
            <div className="stat-card stat-card--purple">
              <div className="stat-number">{meta.clang_count}</div>
              <div className="stat-label">Clang Findings</div>
            </div>
            <div className="stat-card stat-card--red">
              <div className="stat-number">{meta.critical_candidate_count}</div>
              <div className="stat-label">Critical Candidates</div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'all' && (
        <div className="findings-list">
          {allFindings.length === 0 ? (
            <div className="gemini-empty">
              <div className="gemini-empty-title">No Bugs Found!</div>
              <div className="gemini-empty-desc">Your code is completely clean.</div>
            </div>
          ) : (
            allFindings.map((f, i) => {
              const sevClass = f.severity === 'error' ? 'finding-severity--error' : 
                               f.severity === 'warning' ? 'finding-severity--warning' : '';
              const bgColor = f.severity === 'error' ? 'var(--cardinal-red)' : 
                              f.severity === 'warning' ? 'var(--fox-orange)' : 'var(--dodger-blue)';
              
              return (
                <div key={i} className="finding-card" style={{ borderLeft: `5px solid ${bgColor}` }}>
                  <div className="finding-header">
                    <span className="finding-severity" style={{ background: bgColor }}>
                      {f.severity.toUpperCase()}
                    </span>
                    <span className="gemini-badge" style={{ background: 'var(--swan)', color: 'var(--eel)' }}>
                      {f.tool}
                    </span>
                    <span className="finding-location">{extractFilename(f.file)}:{f.line}</span>
                  </div>
                  <div className="finding-category">{f.category}</div>
                  <div style={{ color: 'var(--wolf)', fontWeight: 600 }}>{f.message}</div>
                </div>
              );
            })
          )}
        </div>
      )}

      {activeTab === 'critical' && (
        <div className="findings-list">
          {findings.critical_candidates?.length === 0 ? (
            <div className="gemini-empty">
              <div className="gemini-empty-title">No Critical Candidates!</div>
              <div className="gemini-empty-desc">No bugs were confirmed by both analyzers.</div>
            </div>
          ) : (
            findings.critical_candidates?.map((c, i) => (
              <div key={i} className="finding-card finding-card--critical">
                <div className="finding-header">
                  <span className="finding-severity finding-severity--error">CRITICAL</span>
                  <span className="finding-location">{extractFilename(c.cppcheck.file)}:{c.cppcheck.line}</span>
                </div>
                <div className="finding-category">{c.cppcheck.category} / {c.clang.category}</div>
                <div className="matched-tools">
                  <div className="matched-tool">
                    <div className="matched-tool-name">🔍 Cppcheck</div>
                    <div className="matched-tool-msg">{c.cppcheck.message}</div>
                  </div>
                  <div className="matched-tool">
                    <div className="matched-tool-name">⚙️ Clang</div>
                    <div className="matched-tool-msg">{c.clang.message}</div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'triage' && (
        <div id="gemini-content">
          {!report.gemini_triage || report.gemini_triage.length === 0 ? (
            <div className="gemini-empty">
              <div className="gemini-empty-icon">✨</div>
              <div className="gemini-empty-title">No AI Triage Available</div>
              <div className="gemini-empty-desc">Run the analysis with Gemini AI enabled.</div>
            </div>
          ) : (
            report.gemini_triage.map((t, i) => {
              const g = t.gemini || {};
              const hasError = g.confidence === null;
              const confidence = g.confidence != null ? g.confidence : 0;
              const confPct = Math.round(confidence * 100);
              const confClass = confidence >= 0.7 ? 'confidence-high' : confidence >= 0.4 ? 'confidence-mid' : 'confidence-low';
              const fileInfo = t.cppcheck?.file ? `${extractFilename(t.cppcheck.file)}:${t.cppcheck.line}` : 'unknown file';
              
              return (
                <div key={i} className="gemini-card">
                  <div className="gemini-header">
                    <span className="gemini-badge">✨ Gemini AI</span>
                    {t.is_single && <span className="gemini-badge" style={{background: 'var(--fox-orange)'}}>Single Tool Fallback</span>}
                    <span className="gemini-file" style={{marginLeft: 'auto'}}>{fileInfo}</span>
                  </div>
                  <div className="finding-category" style={{marginBottom:'14px'}}>
                    {t.cppcheck?.category || t.category || 'Unknown Category'}
                  </div>
                  
                  {hasError ? (
                    <>
                      <div className="gemini-section-title">⚠️ API Error</div>
                      <div className="gemini-error">{g.explanation}</div>
                    </>
                  ) : (
                    <>
                      <div className="confidence-meter">
                        <div className="confidence-label">
                          <span className="confidence-text">Confidence</span>
                          <span className="confidence-value">{confPct}%</span>
                        </div>
                        <div className="confidence-track">
                          <div className={`confidence-fill ${confClass}`} style={{width: `${confPct}%`}}></div>
                        </div>
                      </div>
                      <div className="gemini-section" style={{marginBottom:'15px'}}>
                        <div className="gemini-section-title">Explanation</div>
                        <div className="gemini-section-body">{g.explanation}</div>
                      </div>
                      <div className="gemini-section">
                        <div className="gemini-section-title">Suggested Fix</div>
                        <div className="gemini-fix">{g.fix}</div>
                      </div>
                    </>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
