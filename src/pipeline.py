import argparse
import json
import os
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class Finding:
    tool: str
    file: str
    line: int
    severity: str
    category: str
    message: str


def discover_c_files(path: Path) -> List[Path]:
    valid_exts = {".c", ".cpp", ".cc", ".cxx", ".h", ".hpp"}
    if path.is_file() and path.suffix in valid_exts:
        return [path]
    files = []
    for ext in valid_exts:
        files.extend(path.rglob(f"*{ext}"))
    return sorted(files)


def run_cppcheck(files: List[Path]) -> str:
    # Cppcheck usually writes diagnostics to stderr.
    cmd = [
        "cppcheck",
        "--enable=all",
        "--inline-suppr",
        "--suppress=missingIncludeSystem",
        "--template={file}:{line}:{severity}:{id}:{message}",
    ] + [str(f) for f in files]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stderr or ""


def parse_cppcheck_output(raw: str) -> List[Finding]:
    findings: List[Finding] = []
    # Regex handles Windows absolute paths (C:\...) and relative paths
    # Format: <file>:<line>:<severity>:<id>:<message>
    # The file part may contain a drive letter colon like C:\path
    pattern = re.compile(
        r'^(?P<file>.+?):(?P<line>\d+):(?P<severity>[a-z]+):(?P<id>[^:]+):(?P<message>.+)$'
    )
    for line in raw.splitlines():
        # Strip Windows "cppcheck : " prefix
        line = re.sub(r'^cppcheck\s*:\s*', '', line.strip())
        m = pattern.match(line)
        if not m:
            continue
        severity = m.group('severity').strip()
        # Skip non-bug informational lines
        if severity == 'information':
            continue
        findings.append(
            Finding(
                tool="cppcheck",
                file=str(Path(m.group('file').strip())),
                line=int(m.group('line')),
                severity=severity,
                category=m.group('id').strip(),
                message=m.group('message').strip(),
            )
        )
    return findings


def run_clang_analyzer(files: List[Path]) -> str:
    # Run clang analyzer file-by-file to keep output parseable.
    outputs = []
    for f in files:
        cmd = ["clang", "--analyze", str(f)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        combined = "\n".join([result.stdout or "", result.stderr or ""]).strip()
        if combined:
            outputs.append(combined)
    return "\n".join(outputs)


def parse_clang_output(raw: str) -> List[Finding]:
    findings: List[Finding] = []
    # Typical clang diagnostic line:
    # path/file.c:12:5: warning: Dereference of null pointer [core.NullDereference]
    pattern = re.compile(
        r"^(?P<file>.*?):(?P<line>\d+):\d+:\s+warning:\s+(?P<msg>.*?)(?:\s+\[(?P<cat>.*?)\])?$"
    )
    for line in raw.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        category = match.group("cat") or "clang.warning"
        findings.append(
            Finding(
                tool="clang",
                file=str(Path(match.group("file"))),
                line=int(match.group("line")),
                severity="warning",
                category=category,
                message=match.group("msg").strip(),
            )
        )
    return findings


def category_compatible(cat_a: str, cat_b: str) -> bool:
    a = cat_a.lower()
    b = cat_b.lower()
    # Shared keyword in both category names -> compatible
    keywords = [
        "null", "buffer", "overflow", "bounds", "uninit", "memory",
        "leak", "divide", "zero", "free", "scope", "format", "string",
        "deref", "pointer", "integer", "sign",
    ]
    if any(k in a and k in b for k in keywords):
        return True
    # Cross-tool keyword mapping (cppcheck term -> clang term)
    mappings = [
        ("zerodiv",           "dividezero"),
        ("nullpointer",       "nulldereference"),
        ("uninitvar",         "uninitializedvalue"),
        ("bufferaccess",      "arraybound"),
        ("memleak",           "memoryleak"),
        ("danglingpointer",   "deadcode"),
    ]
    for cpp_kw, clang_kw in mappings:
        if cpp_kw in a and clang_kw in b:
            return True
        if clang_kw in a and cpp_kw in b:
            return True
    return False


def match_findings(
    cppcheck_findings: List[Finding],
    clang_findings: List[Finding],
    line_window: int = 5,
) -> Dict[str, Any]:
    matched = []
    cpp_only = []
    clang_used = set()

    for c in cppcheck_findings:
        local_match = None
        for idx, a in enumerate(clang_findings):
            if idx in clang_used:
                continue
            if Path(c.file).name != Path(a.file).name:
                continue
            if abs(c.line - a.line) > line_window:
                continue
            if not category_compatible(c.category, a.category):
                continue
            local_match = (idx, a)
            break
        if local_match:
            idx, a = local_match
            clang_used.add(idx)
            matched.append({"cppcheck": asdict(c), "clang": asdict(a)})
        else:
            cpp_only.append(asdict(c))

    clang_only = [asdict(f) for i, f in enumerate(clang_findings) if i not in clang_used]
    return {
        "critical_candidates": matched,
        "cppcheck_only": cpp_only,
        "clang_only": clang_only,
    }


def read_snippet(file_path: str, line_no: int, radius: int = 3) -> str:
    p = Path(file_path)
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    start = max(0, line_no - 1 - radius)
    end = min(len(lines), line_no + radius)
    snippet = []
    for idx in range(start, end):
        snippet.append(f"{idx + 1}: {lines[idx]}")
    return "\n".join(snippet)


def _call_gemini_with_retry(client, prompt: str, max_retries: int = 4) -> str:
    """Call Gemini API with exponential backoff for rate-limit errors."""
    import time

    # Using gemini-flash-latest which is widely available and supported on the free tier
    model_name = "gemini-flash-latest"
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")
            return response.text.strip()
        except Exception as e:
            err = str(e)
            # Handle rate limits (429) or overloaded (503)
            if ("429" in err or "RESOURCE_EXHAUSTED" in err or "503" in err) and attempt < max_retries - 1:
                wait = 15 * (attempt + 1)
                print(f"  Gemini busy/rate-limited, waiting {wait}s before retry {attempt + 2}/{max_retries}...")
                time.sleep(wait)
            else:
                print(f"  Gemini error on attempt {attempt + 1}: {err}")
                if attempt == max_retries - 1:
                    raise
    return ""


def _parse_gemini_json(raw: str):
    """Extract and parse the JSON from Gemini response text"""
    text = raw.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    # Try to extract a JSON array first (batched), then a single object
    arr_match = re.search(r"\[.*\]", text, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group(0))
        except json.JSONDecodeError:
            pass
    obj_match = re.search(r"\{.*\}", text, re.DOTALL)
    if obj_match:
        return json.loads(obj_match.group(0))
    return json.loads(text)


def gemini_triage(critical_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except Exception:
        return []

    if not critical_candidates:
        return []

    client = genai.Client(api_key=api_key)

    # ── Build ONE batched prompt for ALL candidates ──
    issue_blocks = []
    for idx, candidate in enumerate(critical_candidates):
        cpp = candidate["cppcheck"]
        clang = candidate["clang"]
        snippet = read_snippet(cpp["file"], cpp["line"])
        issue_blocks.append(
            f"--- Issue {idx + 1} ---\n"
            f"Cppcheck: [{cpp['category']}] {cpp['message']} ({cpp['file']}:{cpp['line']})\n"
            f"Clang:    [{clang['category']}] {clang['message']} ({clang['file']}:{clang['line']})\n"
            f"Code:\n{snippet}"
        )

    all_issues = "\n\n".join(issue_blocks)
    prompt = f"""You are a secure C code reviewer.
Below are {len(critical_candidates)} issues that were flagged by BOTH Cppcheck and Clang static analyzers.
For EACH issue, provide: confidence (0-1), explanation (2-4 sentences), and a fix.

{all_issues}

Return a JSON array with exactly {len(critical_candidates)} objects, one per issue, in order:
[{{"confidence": 0.0, "explanation": "...", "fix": "..."}}, ...]
Return ONLY the JSON array, no other text."""

    print(f"  Sending {len(critical_candidates)} candidates to Gemini in 1 batched request...")

    triaged = []
    try:
        raw = _call_gemini_with_retry(client, prompt)
        parsed = _parse_gemini_json(raw)

        # Handle single-object response (if only 1 candidate)
        if isinstance(parsed, dict):
            parsed = [parsed]

        for idx, candidate in enumerate(critical_candidates):
            gemini_result = parsed[idx] if idx < len(parsed) else {
                "confidence": None,
                "explanation": "Gemini did not return a result for this issue.",
                "fix": "Manual review required.",
            }
            triaged.append({
                "cppcheck": candidate["cppcheck"],
                "clang": candidate["clang"],
                "gemini": gemini_result,
            })
        print(f"  Gemini triage complete for {len(triaged)} candidates.")

    except Exception as e:
        print(f"  Gemini API error: {e}")
        # Fall back: attach error to all candidates
        for candidate in critical_candidates:
            triaged.append({
                "cppcheck": candidate["cppcheck"],
                "clang": candidate["clang"],
                "gemini": {
                    "confidence": None,
                    "explanation": f"Gemini API error: {e}",
                    "fix": "Manual review required.",
                },
            })

    return triaged


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def gemini_triage_single(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []
    try:
        from google import genai
    except Exception:
        return []

    if not findings:
        return []

    client = genai.Client(api_key=api_key)

    issue_blocks = []
    for idx, finding in enumerate(findings):
        snippet = read_snippet(finding["file"], finding["line"])
        issue_blocks.append(
            f"--- Issue {idx + 1} ---\n"
            f"Tool: {finding['tool']}\n"
            f"Severity: {finding['severity']}\n"
            f"Category: {finding['category']}\n"
            f"Message: {finding['message']}\n"
            f"Code:\n{snippet}"
        )

    all_issues = "\n\n".join(issue_blocks)
    prompt = f"""You are a secure C code reviewer.
Below are {len(findings)} issues flagged by a static analyzer.
For EACH issue, provide: confidence (0-1), explanation (2-4 sentences), and a fix.

{all_issues}

Return a JSON array with exactly {len(findings)} objects, one per issue, in order:
[{{"confidence": 0.0, "explanation": "...", "fix": "..."}}, ...]
Return ONLY the JSON array, no other text."""

    print(f"  Sending {len(findings)} single-tool findings to Gemini...")

    triaged = []
    try:
        raw = _call_gemini_with_retry(client, prompt)
        parsed = _parse_gemini_json(raw)

        if isinstance(parsed, dict):
            parsed = [parsed]

        for idx, finding in enumerate(findings):
            gemini_result = parsed[idx] if idx < len(parsed) else {
                "confidence": None,
                "explanation": "Gemini did not return a result for this issue.",
                "fix": "Manual review required.",
            }
            triaged.append({
                "cppcheck": finding if finding["tool"] == "cppcheck" else finding,  # Dummy mapping for compatibility with UI
                "clang": finding if finding["tool"] == "clang" else finding,      # Dummy mapping
                "is_single": True,
                "gemini": gemini_result,
            })
    except Exception as e:
        print(f"  Gemini API error: {e}")
    return triaged

def main() -> None:
    parser = argparse.ArgumentParser(description="CS 810 Static Analysis Pipeline Baseline")
    parser.add_argument("--input", required=True, help="C file or directory")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    parser.add_argument("--line-window", type=int, default=5, help="Line match tolerance")
    parser.add_argument("--use-gemini", action="store_true", help="Enable Gemini triage")
    args = parser.parse_args()

    input_path = Path(args.input)
    files = discover_c_files(input_path)
    if not files:
        raise SystemExit("No .c files found to analyze.")

    cpp_raw = run_cppcheck(files)
    clang_raw = run_clang_analyzer(files)
    cpp_findings = parse_cppcheck_output(cpp_raw)
    clang_findings = parse_clang_output(clang_raw)
    fused = match_findings(cpp_findings, clang_findings, line_window=args.line_window)

    report: Dict[str, Any] = {
        "meta": {
            "input": str(input_path),
            "file_count": len(files),
            "cppcheck_count": len(cpp_findings),
            "clang_count": len(clang_findings),
            "critical_candidate_count": len(fused["critical_candidates"]),
        },
        "findings": fused,
    }

    if args.use_gemini:
        # Triage critical candidates (matched by both tools)
        triaged_critical = gemini_triage(fused["critical_candidates"])
        
        # If the user has no critical bugs, only triage a maximum of 2 single bugs 
        # to keep the API call extremely fast and light.
        triaged_singles = []
        if not triaged_critical:
            singles = [f for f in fused["cppcheck_only"] + fused["clang_only"] 
                       if f.get("severity") in ("error", "warning")]
            
            singles.sort(key=lambda x: 0 if x.get("severity") == "error" else 1)
            triaged_singles = gemini_triage_single(singles[:2])
            
        report["gemini_triage"] = triaged_critical + triaged_singles
        
        if not report["gemini_triage"]:
            print("  [INFO] No significant bugs found to triage with AI.")

    out_path = Path(args.output)
    ensure_parent_dir(out_path)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to: {out_path}")

if __name__ == "__main__":
    main()
