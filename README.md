# CS 810 Final Project Baseline

## Team
- Dimitrios Stamoutsos
- Michael Lamaze
- Christian Lencsak

## Project Goal
Build a static analysis workflow that combines:
1. `Cppcheck`
2. A second static analyzer (`clang --analyze`)
3. Optional Gemini API post-processing for human-readable triage and fix guidance

The key idea is to reduce false positives and make results more actionable by:
- Cross-validating findings between two analyzers
- Highlighting overlap as high-confidence/critical candidates
- Using an LLM to explain likely root cause, confidence, and suggested fix

## What This Baseline Includes
- A reproducible project structure
- Sample vulnerable C programs for testing
- A Python pipeline scaffold that:
  - Runs both analyzers
  - Parses findings into a unified schema
  - Matches overlapping findings
  - Produces a single JSON report
  - Optionally asks Gemini for analysis on overlapping findings
- A project plan and evaluation criteria

## Proposed Workflow
1. Analyze target C files with Cppcheck.
2. Analyze the same files with Clang static analyzer.
3. Normalize findings into one format.
4. Match findings by file + line proximity + issue category.
5. Label matched findings as `critical_candidate`.
6. Send matched code snippets to Gemini for confidence + remediation advice.
7. Present all findings in a unified report:
   - Matched (`critical_candidate`)
   - Cppcheck-only
   - Clang-only

## Prerequisites
- Python 3.10+
- Cppcheck installed and available in PATH
- Clang installed and available in PATH (`clang --analyze`)
- (Optional) Gemini API key for AI triage

## Quick Start
1. Install Python dependencies:
   - `pip install -r requirements.txt`
2. Run baseline on sample programs:
   - `python src/pipeline.py --input samples --output reports/baseline_report.json`
3. Enable Gemini triage (optional):
   - Set env var: `GEMINI_API_KEY=your_key_here`
   - Run with: `--use-gemini`

Example:
`python src/pipeline.py --input samples --output reports/baseline_report.json --use-gemini`

## Deliverables You Can Build From Here
- Comparative effectiveness analysis (precision proxy, overlap rate, missed categories)
- Error taxonomy by vulnerability type
- LLM usefulness study (quality of fix guidance, agreement with human judgment)
- Extended scoring/ranking model for finding priority

## Suggested Work Split
- **Dimitrios**: pipeline integration + report generation
- **Michael**: benchmark program set + ground truth labeling
- **Christian**: Gemini prompt engineering + evaluation write-up

## Notes
- This baseline is intentionally minimal but runnable.
- Extend parsers and matching logic as you gather more real outputs.
- For final paper/demo, include both successful detections and failure cases.
