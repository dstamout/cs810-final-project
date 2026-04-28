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


def discover_c_files(input_path: Path) -> List[Path]:
    if input_path.is_file() and input_path.suffix == ".c":
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.rglob("*.c"))
    return []


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
    for line in raw.splitlines():
        # Expected format: file:line:severity:id:message
        parts = line.split(":", 4)
        if len(parts) < 5:
            continue
        file_path, line_no, severity, category, message = parts
        if not line_no.isdigit():
            continue
        findings.append(
            Finding(
                tool="cppcheck",
                file=str(Path(file_path)),
                line=int(line_no),
                severity=severity.strip(),
                category=category.strip(),
                message=message.strip(),
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
    keywords = ["null", "buffer", "overflow", "bounds", "uninit", "memory", "leak"]
    return any(k in a and k in b for k in keywords) or a == b


def match_findings(
    cppcheck_findings: List[Finding],
    clang_findings: List[Finding],
    line_window: int = 2,
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


def gemini_triage(critical_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return []
    try:
        import google.generativeai as genai  # type: ignore
    except Exception:
        return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    triaged = []
    for candidate in critical_candidates:
        cpp = candidate["cppcheck"]
        clang = candidate["clang"]
        snippet = read_snippet(cpp["file"], cpp["line"])
        prompt = f"""
You are a secure C code reviewer.
Given two static analyzer findings for likely the same issue, provide:
1) confidence score between 0 and 1
2) brief explanation (2-4 sentences)
3) concrete fix recommendation

Cppcheck:
- category: {cpp["category"]}
- message: {cpp["message"]}
- file: {cpp["file"]}
- line: {cpp["line"]}

Clang:
- category: {clang["category"]}
- message: {clang["message"]}
- file: {clang["file"]}
- line: {clang["line"]}

Code snippet:
{snippet}

Return strict JSON only:
{{"confidence": 0.0, "explanation": "...", "fix": "..."}}
"""
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            parsed = json.loads(text)
            triaged.append(
                {
                    "cppcheck": cpp,
                    "clang": clang,
                    "gemini": parsed,
                }
            )
        except Exception:
            triaged.append(
                {
                    "cppcheck": cpp,
                    "clang": clang,
                    "gemini": {
                        "confidence": None,
                        "explanation": "Gemini parsing failed for this finding.",
                        "fix": "Manual review required.",
                    },
                }
            )
    return triaged


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="CS 810 Static Analysis Pipeline Baseline")
    parser.add_argument("--input", required=True, help="C file or directory")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    parser.add_argument("--line-window", type=int, default=2, help="Line match tolerance")
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
        report["gemini_triage"] = gemini_triage(fused["critical_candidates"])

    out_path = Path(args.output)
    ensure_parent_dir(out_path)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to: {out_path}")


if __name__ == "__main__":
    main()
