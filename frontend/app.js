/**
 * BugHunter — CS810 Static Analysis Dashboard
 * Duolingo-inspired gamified frontend for viewing analysis reports.
 */

// ── State ──
let reportData = null;
let allFindings = [];

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => {
  setupNavigation();
  setupModal();
  fetchReport();
});

// ── Navigation ──
function setupNavigation() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const view = btn.dataset.view;
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      const target = document.getElementById(`view-${view}`);
      if (target) target.classList.add('active');
    });
  });
}

// ── Modal ──
function setupModal() {
  const overlay = document.getElementById('modal-overlay');
  const closeBtn = document.getElementById('modal-close');
  closeBtn.addEventListener('click', () => overlay.classList.remove('open'));
  overlay.addEventListener('click', e => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
  const closeViewer = document.getElementById('btn-close-viewer');
  if (closeViewer) {
    closeViewer.addEventListener('click', () => {
      document.getElementById('code-viewer-container').style.display = 'none';
    });
  }
}

function showModal(title, htmlContent) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = htmlContent;
  document.getElementById('modal-overlay').classList.add('open');
}

// ── Data Fetch ──
async function fetchReport() {
  try {
    const res = await fetch('/api/report');
    reportData = await res.json();
    if (reportData.error) {
      showEmptyState();
      return;
    }
    processReport();
  } catch (err) {
    console.error('Failed to load report:', err);
    showEmptyState();
  }
}

function showEmptyState() {
  document.getElementById('stat-files-num').textContent = '0';
  document.getElementById('stat-cppcheck-num').textContent = '0';
  document.getElementById('stat-clang-num').textContent = '0';
  document.getElementById('stat-critical-num').textContent = '0';
}

// ── Process Report ──
function processReport() {
  const meta = reportData.meta;
  const findings = reportData.findings;

  // Flatten all findings
  allFindings = [];
  (findings.cppcheck_only || []).forEach(f => allFindings.push(f));
  (findings.clang_only || []).forEach(f => allFindings.push(f));

  // Update badges
  const critCount = (findings.critical_candidates || []).length;
  const totalCount = allFindings.length + critCount * 2;
  document.getElementById('badge-critical').textContent = critCount;
  document.getElementById('badge-findings').textContent = totalCount;

  // Update stat cards with animation
  animateNumber('stat-files-num', meta.file_count);
  animateNumber('stat-cppcheck-num', meta.cppcheck_count);
  animateNumber('stat-clang-num', meta.clang_count);
  animateNumber('stat-critical-num', meta.critical_candidate_count);

  // Security score (higher = more bugs = lower score)
  const errorCount = allFindings.filter(f => f.severity === 'error').length;
  const maxErrors = Math.max(totalCount, 1);
  const score = Math.max(0, Math.round(100 - (errorCount / maxErrors) * 100));
  document.getElementById('xp-value').textContent = `${score}/100`;
  setTimeout(() => {
    document.getElementById('xp-fill').style.width = `${score}%`;
  }, 300);

  // Render all sections
  renderSeverityBars();
  renderHeatmap();
  renderCriticalList();
  renderFindingsList();
  renderGeminiView();
  renderFilesView();
  setupFilters();
}

// ── Animate Number ──
function animateNumber(elemId, target) {
  const el = document.getElementById(elemId);
  const duration = 800;
  const start = performance.now();
  const initial = 0;

  function tick(now) {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(initial + (target - initial) * eased);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

// ── Severity Bars ──
function renderSeverityBars() {
  const container = document.getElementById('severity-bars');
  const counts = { error: 0, warning: 0, style: 0, information: 0 };

  allFindings.forEach(f => {
    const sev = f.severity || 'information';
    if (counts[sev] !== undefined) counts[sev]++;
    else counts.information++;
  });

  const max = Math.max(...Object.values(counts), 1);
  container.innerHTML = '';

  for (const [sev, count] of Object.entries(counts)) {
    const pct = (count / max) * 100;
    const row = document.createElement('div');
    row.className = 'severity-bar-row';
    row.innerHTML = `
      <span class="severity-bar-label" style="color: var(--${sevColor(sev)})">${sev}</span>
      <div class="severity-bar-track">
        <div class="severity-bar-fill severity-bar-fill--${sev}" style="width: 0%"></div>
      </div>
      <span class="severity-bar-count">${count}</span>
    `;
    container.appendChild(row);
    // Animate
    setTimeout(() => {
      row.querySelector('.severity-bar-fill').style.width = `${pct}%`;
    }, 200);
  }
}

function sevColor(sev) {
  const map = { error: 'cardinal-red', warning: 'fox-orange', style: 'dodger-blue', information: 'hare' };
  return map[sev] || 'hare';
}

// ── Heatmap ──
function renderHeatmap() {
  const container = document.getElementById('heatmap-grid');
  const fileCounts = {};

  allFindings.forEach(f => {
    const name = extractFilename(f.file);
    fileCounts[name] = (fileCounts[name] || 0) + 1;
  });

  // Also count critical candidates
  (reportData.findings.critical_candidates || []).forEach(c => {
    const name = extractFilename(c.cppcheck.file);
    fileCounts[name] = (fileCounts[name] || 0) + 2;
  });

  const entries = Object.entries(fileCounts).sort((a, b) => b[1] - a[1]);
  const maxCount = entries.length ? entries[0][1] : 0;

  container.innerHTML = '';
  entries.forEach(([name, count]) => {
    const heat = maxCount === 0 ? 0 : Math.min(3, Math.floor((count / maxCount) * 3.99));
    const cell = document.createElement('div');
    cell.className = `heatmap-cell heat-${heat}`;
    cell.innerHTML = `
      <div class="heatmap-filename">📄 ${name}</div>
      <div class="heatmap-count">${count}</div>
      <div class="heatmap-label">issues</div>
    `;
    cell.addEventListener('click', () => {
      document.querySelector('[data-view="findings"]').click();
    });
    container.appendChild(cell);
  });
}

function extractFilename(filepath) {
  if (!filepath) return 'unknown';
  return filepath.replace(/\\/g, '/').split('/').pop();
}

// ── Critical List ──
function renderCriticalList() {
  const container = document.getElementById('critical-list');
  const candidates = reportData.findings.critical_candidates || [];
  container.innerHTML = '';

  if (candidates.length === 0) {
    container.innerHTML = `
      <div class="gemini-empty">
        <div class="gemini-empty-icon">🎉</div>
        <div class="gemini-empty-title">No Critical Candidates!</div>
        <div class="gemini-empty-desc">No bugs were confirmed by both analyzers.</div>
      </div>
    `;
    return;
  }

  candidates.forEach((c, i) => {
    const card = document.createElement('div');
    card.className = 'finding-card finding-card--critical';
    card.innerHTML = `
      <div class="finding-header">
        <span class="finding-severity finding-severity--error">CRITICAL</span>
        <span class="finding-location">${extractFilename(c.cppcheck.file)}:${c.cppcheck.line}</span>
      </div>
      <div class="finding-category">${c.cppcheck.category} / ${c.clang.category}</div>
      <div class="matched-tools">
        <div class="matched-tool">
          <div class="matched-tool-name">🔍 Cppcheck</div>
          <div class="matched-tool-msg">${escapeHtml(c.cppcheck.message)}</div>
        </div>
        <div class="matched-tool">
          <div class="matched-tool-name">⚙️ Clang</div>
          <div class="matched-tool-msg">${escapeHtml(c.clang.message)}</div>
        </div>
      </div>
    `;
    card.addEventListener('click', () => {
      loadSourceInModal(c.cppcheck.file, c.cppcheck.line);
    });
    container.appendChild(card);
  });
}

// ── All Findings ──
function renderFindingsList(filter = 'all') {
  const container = document.getElementById('findings-list');
  container.innerHTML = '';

  let filtered = [...allFindings];
  if (filter === 'error' || filter === 'warning' || filter === 'style') {
    filtered = filtered.filter(f => f.severity === filter);
  } else if (filter === 'cppcheck') {
    filtered = filtered.filter(f => f.tool === 'cppcheck');
  } else if (filter === 'clang') {
    filtered = filtered.filter(f => f.tool === 'clang');
  }

  // Sort: errors first, then warnings, then style
  const sevOrder = { error: 0, warning: 1, style: 2, information: 3 };
  filtered.sort((a, b) => (sevOrder[a.severity] ?? 9) - (sevOrder[b.severity] ?? 9));

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="gemini-empty">
        <div class="gemini-empty-icon">🔎</div>
        <div class="gemini-empty-title">No findings match this filter</div>
        <div class="gemini-empty-desc">Try a different filter to see results.</div>
      </div>
    `;
    return;
  }

  filtered.forEach(f => {
    const card = document.createElement('div');
    card.className = 'finding-card';
    card.innerHTML = `
      <div class="finding-header">
        <span class="finding-severity finding-severity--${f.severity}">${f.severity}</span>
        <span class="finding-tool">${f.tool}</span>
        <span class="finding-location">${extractFilename(f.file)}:${f.line}</span>
      </div>
      <div class="finding-category">${f.category}</div>
      <div class="finding-message">${escapeHtml(f.message)}</div>
    `;
    card.addEventListener('click', () => {
      loadSourceInModal(f.file, f.line);
    });
    container.appendChild(card);
  });
}

function setupFilters() {
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderFindingsList(btn.dataset.filter);
    });
  });
}

// ── Gemini View ──
function renderGeminiView() {
  const container = document.getElementById('gemini-content');
  const triaged = reportData.gemini_triage;

  if (!triaged || triaged.length === 0) {
    container.innerHTML = `
      <div class="gemini-empty">
        <div class="gemini-empty-icon">✨</div>
        <div class="gemini-empty-title">No AI Triage Available</div>
        <div class="gemini-empty-desc">Run the pipeline with <code>--use-gemini</code> to enable Gemini AI analysis.<br>
        <code style="margin-top:8px;display:inline-block;background:#f3f4f6;padding:6px 12px;border-radius:8px;font-size:0.85rem;">
          python src/pipeline.py --input samples --output reports/gemini_report.json --use-gemini
        </code></div>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  triaged.forEach(t => {
    const g = t.gemini || {};
    const hasError = g.confidence === null;
    const confidence = g.confidence != null ? g.confidence : 0;
    const confPct = Math.round(confidence * 100);
    const confClass = confidence >= 0.7 ? 'confidence-high' : confidence >= 0.4 ? 'confidence-mid' : 'confidence-low';

    const card = document.createElement('div');
    card.className = 'gemini-card';

    let bodyHtml = '';
    if (hasError) {
      bodyHtml = `
        <div class="gemini-section">
          <div class="gemini-section-title">⚠️ API Error</div>
          <div class="gemini-error">${escapeHtml(truncate(g.explanation, 200))}</div>
        </div>
        <div class="gemini-section">
          <div class="gemini-section-title">Recommendation</div>
          <div class="gemini-section-body">${escapeHtml(g.fix)}</div>
        </div>
      `;
    } else {
      bodyHtml = `
        <div class="confidence-meter">
          <div class="confidence-label">
            <span class="confidence-text">Confidence</span>
            <span class="confidence-value" style="color: ${confColor(confidence)}">${confPct}%</span>
          </div>
          <div class="confidence-track">
            <div class="confidence-fill ${confClass}" style="width: ${confPct}%"></div>
          </div>
        </div>
        <div class="gemini-section">
          <div class="gemini-section-title">Explanation</div>
          <div class="gemini-section-body">${escapeHtml(g.explanation)}</div>
        </div>
        <div class="gemini-section">
          <div class="gemini-section-title">Suggested Fix</div>
          <div class="gemini-fix">${escapeHtml(g.fix)}</div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="gemini-header">
        <span class="gemini-badge">✨ Gemini AI</span>
        <span class="gemini-file">${extractFilename(t.cppcheck.file)}:${t.cppcheck.line}</span>
      </div>
      <div class="finding-category" style="margin-bottom: 14px;">
        ${t.cppcheck.category} → ${escapeHtml(t.cppcheck.message)}
      </div>
      ${bodyHtml}
    `;
    container.appendChild(card);
  });
}

function confColor(v) {
  if (v >= 0.7) return 'var(--feather-green)';
  if (v >= 0.4) return 'var(--fox-orange)';
  return 'var(--cardinal-red)';
}

// ── Files View ──
function renderFilesView() {
  const container = document.getElementById('file-cards');
  const fileSet = new Set();

  allFindings.forEach(f => fileSet.add(f.file));
  (reportData.findings.critical_candidates || []).forEach(c => {
    fileSet.add(c.cppcheck.file);
  });

  container.innerHTML = '';
  [...fileSet].sort().forEach(filepath => {
    const name = extractFilename(filepath);
    const count = allFindings.filter(f => extractFilename(f.file) === name).length;
    const card = document.createElement('div');
    card.className = 'file-card';
    card.innerHTML = `
      <div class="file-card-name">📄 ${name}</div>
      <div class="file-card-stats">${count} finding${count !== 1 ? 's' : ''} · Click to view source</div>
    `;
    card.addEventListener('click', () => loadSourceViewer(filepath));
    container.appendChild(card);
  });
}

// ── Source Code Viewer ──
async function loadSourceViewer(filepath) {
  const container = document.getElementById('code-viewer-container');
  const viewer = document.getElementById('code-viewer');
  const filename = document.getElementById('code-viewer-filename');

  filename.textContent = extractFilename(filepath);
  container.style.display = 'block';
  viewer.innerHTML = '<span class="shimmer" style="display:block;height:200px;"></span>';

  try {
    const normalizedPath = filepath.replace(/\\/g, '/');
    const res = await fetch(`/api/source/${normalizedPath}`);
    const data = await res.json();

    if (data.error) {
      viewer.textContent = data.error;
      return;
    }

    // Collect flagged lines for this file
    const flaggedLines = new Set();
    const fname = extractFilename(filepath);
    allFindings.forEach(f => {
      if (extractFilename(f.file) === fname) flaggedLines.add(f.line);
    });
    (reportData.findings.critical_candidates || []).forEach(c => {
      if (extractFilename(c.cppcheck.file) === fname) {
        flaggedLines.add(c.cppcheck.line);
      }
    });

    const lines = data.content.split('\n');
    viewer.innerHTML = lines.map((line, i) => {
      const lineNum = i + 1;
      const flagged = flaggedLines.has(lineNum) ? ' code-line--flagged' : '';
      return `<span class="code-line${flagged}"><span class="code-line-num">${lineNum}</span>${escapeHtml(line)}</span>`;
    }).join('\n');

  } catch (err) {
    viewer.textContent = `Error loading source: ${err.message}`;
  }
}

async function loadSourceInModal(filepath, line) {
  const fname = extractFilename(filepath);
  const normalizedPath = filepath.replace(/\\/g, '/');

  try {
    const res = await fetch(`/api/source/${normalizedPath}`);
    const data = await res.json();

    if (data.error) {
      showModal(fname, `<p class="gemini-error">${data.error}</p>`);
      return;
    }

    const flaggedLines = new Set();
    allFindings.forEach(f => {
      if (extractFilename(f.file) === fname) flaggedLines.add(f.line);
    });
    (reportData.findings.critical_candidates || []).forEach(c => {
      if (extractFilename(c.cppcheck.file) === fname) {
        flaggedLines.add(c.cppcheck.line);
      }
    });

    const lines = data.content.split('\n');
    const html = `<pre class="code-viewer">${lines.map((l, i) => {
      const ln = i + 1;
      const flagged = flaggedLines.has(ln) ? ' code-line--flagged' : '';
      return `<span class="code-line${flagged}"><span class="code-line-num">${ln}</span>${escapeHtml(l)}</span>`;
    }).join('\n')}</pre>`;

    showModal(`📄 ${fname} — Line ${line}`, html);

  } catch (err) {
    showModal(fname, `<p class="gemini-error">Failed to load source: ${err.message}</p>`);
  }
}

// ── Helpers ──
function escapeHtml(str) {
  if (!str) return '';
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function truncate(str, max) {
  if (!str || str.length <= max) return str;
  return str.slice(0, max) + '…';
}
