# Project Baseline and Scope

## Problem Statement
Single static analyzers often generate false positives and miss real bugs. This project explores whether combining two analyzers plus LLM-assisted triage improves practical usefulness for developers.

## Research Questions
1. Does overlap between Cppcheck and Clang analyzer improve confidence in findings?
2. What vulnerability categories are consistently found or missed?
3. Does Gemini-generated remediation guidance improve interpretability/actionability?

## Baseline System Design
- **Input**: One C file or a directory of C files.
- **Analyzer A**: Cppcheck (`--enable=all`).
- **Analyzer B**: Clang static analyzer (`clang --analyze`).
- **Fusion**:
  - Parse findings into common schema:
    - `tool`, `file`, `line`, `severity`, `message`, `category`
  - Match candidates by:
    - Same file
    - Line distance threshold (default ±2)
    - Same/compatible category
- **AI Triage (optional)**:
  - For matched findings only
  - Send local code snippet + finding metadata to Gemini
  - Receive:
    - confidence score (0-1)
    - short explanation
    - suggested fix
- **Output**: JSON unified report, easy to post-process.

## Initial Evaluation Metrics
- Number of findings by tool
- Overlap count and overlap ratio
- Category distribution
- Manual validation sample:
  - True positive estimate by category
  - False positive estimate by category
- Gemini utility rubric:
  - Correctness of explanation
  - Practicality of fix suggestion
  - Confidence calibration quality

## Stretch Goals
- Add a third analyzer for triangulation
- Add lightweight UI/report viewer
- Add deterministic scoring model:
  - Base severity
  - Overlap bonus
  - LLM confidence weighting
- Compare prompt variants and evaluate consistency
