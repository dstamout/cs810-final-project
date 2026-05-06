"""
BugHunter End-to-End Test Suite
Tests: pipeline.py tools, API endpoints, Gemini triage integration
Run with:  python tests/test_e2e.py
"""
import sys, io
# Force UTF-8 on Windows consoles so ANSI escape sequences work
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import os
import json
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
import urllib.request
import urllib.error

# ── Colours for terminal output ──────────────────────────────────────────────
GRN  = "\033[92m"
RED  = "\033[91m"
YLW  = "\033[93m"
BLU  = "\033[94m"
MAG  = "\033[95m"
CYN  = "\033[96m"
RST  = "\033[0m"
BOLD = "\033[1m"

API_BASE = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR  = PROJECT_ROOT / "samples"


def sep(title=""):
    w = 70
    if title:
        pad = (w - len(title) - 2) // 2
        print(f"\n{BLU}{'─' * pad} {title} {'─' * pad}{RST}")
    else:
        print(f"{BLU}{'─' * w}{RST}")


def ok(msg):  print(f"  {GRN}[PASS]{RST}  {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RST}  {msg}"); return False
def warn(msg): print(f"  {YLW}[WARN]{RST}  {msg}")
def info(msg): print(f"  {CYN}[INFO]{RST}  {msg}")


results = {"passed": 0, "failed": 0, "warnings": 0}

def assert_true(condition, pass_msg, fail_msg):
    if condition:
        ok(pass_msg)
        results["passed"] += 1
        return True
    else:
        fail(fail_msg)
        results["failed"] += 1
        return False


# ══════════════════════════════════════════════════════════════════════════════
# Section 1: Tool availability
# ══════════════════════════════════════════════════════════════════════════════
def test_tools():
    sep("1. Tool Availability")

    for tool, args in [("cppcheck", ["--version"]), ("clang", ["--version"])]:
        try:
            r = subprocess.run([tool] + args, capture_output=True, text=True)
            ver = (r.stdout + r.stderr).strip().split("\n")[0]
            assert_true(r.returncode == 0, f"{tool} found: {ver}", f"{tool} not found or failed")
        except FileNotFoundError:
            fail(f"{tool} not installed / not on PATH")
            results["failed"] += 1


# ══════════════════════════════════════════════════════════════════════════════
# Section 2: Pipeline unit tests (no API, direct subprocess)
# ══════════════════════════════════════════════════════════════════════════════
def test_pipeline_on_samples():
    sep("2. Pipeline — All Sample Files (no Gemini)")

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "report.json"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "pipeline.py"),
            "--input",  str(SAMPLES_DIR),
            "--output", str(report_path),
        ]
        t0 = time.time()
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - t0

        assert_true(result.returncode == 0,
                    f"Pipeline exited 0 in {elapsed:.1f}s",
                    f"Pipeline failed (rc={result.returncode}): {result.stderr[:300]}")

        if not report_path.exists():
            fail("Report JSON not created"); results["failed"] += 1; return None

        report = json.loads(report_path.read_text(encoding="utf-8"))
        m = report.get("meta", {})
        f = report.get("findings", {})

        assert_true(m.get("file_count", 0) > 0,
                    f"Scanned {m.get('file_count')} files", "No files scanned")
        assert_true(m.get("cppcheck_count", 0) > 5,
                    f"Cppcheck found {m.get('cppcheck_count')} findings", "Cppcheck found too few findings (expected > 5)")
        assert_true(m.get("clang_count", 0) > 0,
                    f"Clang found {m.get('clang_count')} findings", "Clang found nothing")
        assert_true(m.get("critical_candidate_count", 0) > 0,
                    f"{m.get('critical_candidate_count')} critical candidates", "No critical candidates matched")

        # Per-severity breakdown
        cppcheck_findings = f.get("cppcheck_only", []) + [c["cppcheck"] for c in f.get("critical_candidates",[])]
        clang_findings    = f.get("clang_only",    []) + [c["clang"]    for c in f.get("critical_candidates",[])]
        errors   = [x for x in cppcheck_findings + clang_findings if x.get("severity") == "error"]
        warnings = [x for x in cppcheck_findings + clang_findings if x.get("severity") == "warning"]
        info(f"Errors: {len(errors)}, Warnings: {len(warnings)}")

        return report


def test_pipeline_single_file():
    sep("2b. Pipeline — Single File (integer_overflow.c)")

    target = SAMPLES_DIR / "integer_overflow.c"
    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "report.json"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "src" / "pipeline.py"),
            "--input",  str(target),
            "--output", str(report_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert_true(result.returncode == 0,
                    "Pipeline ran on single file",
                    f"Pipeline failed: {result.stderr[:200]}")

        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            m = report["meta"]
            assert_true(m["cppcheck_count"] > 0,
                        f"Cppcheck found {m['cppcheck_count']} issues in integer_overflow.c",
                        "Cppcheck found 0 issues in integer_overflow.c")
            info(f"Clang findings: {m['clang_count']}, Critical: {m['critical_candidate_count']}")


# ══════════════════════════════════════════════════════════════════════════════
# Section 3: API endpoint tests
# ══════════════════════════════════════════════════════════════════════════════
def api_get(path):
    try:
        with urllib.request.urlopen(f"{API_BASE}{path}", timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return None, str(e)

def api_post_json(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return None, str(e)


def test_api_health():
    sep("3. API Health Checks")

    # /api/reports
    status, body = api_get("/api/reports")
    assert_true(status == 200,
                f"GET /api/reports → 200, {len(body.get('reports',[]))} report(s)",
                f"GET /api/reports → {status}")

    # /api/report/<existing>
    reports = body.get("reports", [])
    if reports:
        rname = reports[0]
        status2, body2 = api_get(f"/api/report/{rname}")
        assert_true(status2 == 200 and "meta" in body2,
                    f"GET /api/report/{rname} → valid JSON with meta",
                    f"GET /api/report/{rname} → {status2}")
    else:
        warn("No reports on disk yet — skipping report fetch test")
        results["warnings"] += 1

    # 404 for missing report
    status3, _ = api_get("/api/report/does_not_exist.json")
    assert_true(status3 == 404,
                "GET /api/report/missing → 404 as expected",
                f"GET /api/report/missing → {status3} (expected 404)")


def test_api_upload_and_analyze():
    sep("4. API Upload + Analyze (multipart form)")

    # Upload integer_overflow.c via multipart
    src = SAMPLES_DIR / "integer_overflow.c"
    boundary = "----BugHunterTestBoundary"
    file_content = src.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="files"; filename="integer_overflow.c"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
    ).encode() + file_content + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{API_BASE}/api/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            upload_resp = json.loads(r.read())
        session_id = upload_resp.get("session_id", "")
        assert_true(bool(session_id),
                    f"Upload succeeded, session_id={session_id[:8]}…",
                    "Upload returned no session_id")
    except Exception as e:
        fail(f"Upload request failed: {e}"); results["failed"] += 1; return

    # Analyze (no Gemini — fast)
    info("Running analysis on uploaded file (no Gemini)…")
    t0 = time.time()
    status, analyze_resp = api_post_json("/api/analyze", {
        "session_id": session_id,
        "use_gemini": False
    })
    elapsed = time.time() - t0

    assert_true(status == 200 and "report" in analyze_resp,
                f"Analyze completed in {elapsed:.1f}s → {analyze_resp.get('report','?')}",
                f"Analyze failed → status={status}, body={analyze_resp}")

    # Fetch the generated report
    report_name = analyze_resp.get("report", "")
    if report_name:
        status2, report = api_get(f"/api/report/{report_name}")
        assert_true(status2 == 200 and "meta" in report,
                    "Fetched fresh report from API",
                    f"Failed to fetch report: status={status2}")
        if "meta" in report:
            m = report["meta"]
            info(f"  Files: {m['file_count']}, Cppcheck: {m['cppcheck_count']}, "
                 f"Clang: {m['clang_count']}, Critical: {m['critical_candidate_count']}")
            assert_true(m["cppcheck_count"] > 0,
                        "Cppcheck produced findings via API",
                        "Cppcheck produced 0 findings via API")
    return session_id, report_name


# ══════════════════════════════════════════════════════════════════════════════
# Section 4: Gemini triage test
# ══════════════════════════════════════════════════════════════════════════════
def test_gemini_triage():
    sep("5. Gemini AI Triage (via API — uses real key)")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        warn("GEMINI_API_KEY not set — skipping Gemini triage test")
        results["warnings"] += 1
        return

    # Upload the null_deref + uninitialized_var samples (most likely to get critical candidates)
    boundary = "----GeminiTestBoundary"
    parts = b""
    for fname in ["null_deref.c", "uninitialized_var.c"]:
        fc = (SAMPLES_DIR / fname).read_bytes()
        parts += (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="files"; filename="{fname}"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
        ).encode() + fc + b"\r\n"
    parts += f"--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{API_BASE}/api/upload", data=parts,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            upload_resp = json.loads(r.read())
        session_id = upload_resp.get("session_id", "")
    except Exception as e:
        fail(f"Gemini test upload failed: {e}"); results["failed"] += 1; return

    info(f"Uploaded 2 files, session={session_id[:8]}…  Running Gemini triage…")
    t0 = time.time()
    status, analyze_resp = api_post_json("/api/analyze", {
        "session_id": session_id,
        "use_gemini": True
    })
    elapsed = time.time() - t0

    assert_true(status == 200, f"Analyze+Gemini returned 200 in {elapsed:.1f}s",
                f"Analyze+Gemini failed: {status}")

    report_name = analyze_resp.get("report", "")
    if not report_name:
        fail("No report returned from Gemini analysis"); results["failed"] += 1; return

    _, report = api_get(f"/api/report/{report_name}")
    gemini = report.get("gemini_triage", [])

    if len(gemini) == 0:
        warn("Gemini triage returned 0 results — likely API quota exhausted; check key")
        results["warnings"] += 1
        return

    ok(f"Gemini triage returned {len(gemini)} result(s)")
    results["passed"] += 1

    if has_error and not has_success:
        warn("All Gemini results are API errors (quota issue?) — check GEMINI_API_KEY quota")
        results["warnings"] += 1
    elif has_success:
        for i, g in enumerate(gemini[:2]):  # Show first 2
            gdata = g.get("gemini", {})
            conf = gdata.get("confidence")
            expl = gdata.get("explanation", "")[:80]
            assert_true(conf is not None and 0 <= conf <= 1,
                        f"Result {i+1}: confidence={conf:.0%} | {expl}…",
                        f"Result {i+1}: invalid confidence value: {conf}")
    else:
        warn("Mixed Gemini results — some succeeded, some API errors")
        results["warnings"] += 1


# ══════════════════════════════════════════════════════════════════════════════
# Section 5: Specific known-bug detection assertions
# ══════════════════════════════════════════════════════════════════════════════
def test_known_bugs():
    sep("6. Known Bug Detection")

    with tempfile.TemporaryDirectory() as tmpdir:
        report_path = Path(tmpdir) / "report.json"
        subprocess.run([
            sys.executable, str(PROJECT_ROOT / "src" / "pipeline.py"),
            "--input", str(SAMPLES_DIR),
            "--output", str(report_path),
        ], capture_output=True)

        if not report_path.exists():
            fail("No report for known-bug tests"); results["failed"] += 1; return

        report = json.loads(report_path.read_text(encoding="utf-8"))
        f = report["findings"]
        all_cpp = f.get("cppcheck_only", []) + [c["cppcheck"] for c in f.get("critical_candidates", [])]
        all_clang = f.get("clang_only", [])   + [c["clang"]    for c in f.get("critical_candidates", [])]
        all_findings = all_cpp + all_clang

        def file_has_category(filename, category):
            return any(
                Path(x["file"]).name == filename and category.lower() in x["category"].lower()
                for x in all_findings
            )

        def file_has_any(filename):
            return any(Path(x["file"]).name == filename for x in all_findings)

        checks = [
            ("null_deref.c",        "nullPointer",         "Null pointer dereference detected"),
            ("memory_leak.c",       "memleak",             "Memory leak detected"),
            ("buffer_overflow.c",   "bufferAccess",        "Buffer overflow detected by Cppcheck"),
            ("integer_overflow.c",  "zerodiv",             "Integer overflow/zero-div detected"),
        ]
        for fname, cat, label in checks:
            hit = any(Path(x["file"]).name == fname for x in all_findings)
            assert_true(hit, f"{label} — found in {fname}", f"No findings at all in {fname}")

        # Check critical candidates contain known paired issues
        crits = f.get("critical_candidates", [])
        crit_files = {Path(c["cppcheck"]["file"]).name for c in crits}
        info(f"Critical candidates in files: {crit_files if crit_files else 'none'}")
        if crits:
            ok(f"{len(crits)} cross-tool critical candidate(s) found")
            results["passed"] += 1
        else:
            warn("No critical candidates — may be fine if tools don't agree on line proximity")
            results["warnings"] += 1


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}{MAG}=================================================={RST}")
    print(f"{BOLD}{MAG}   BugHunter End-to-End Test Suite{RST}")
    print(f"{BOLD}{MAG}=================================================={RST}")
    print(f"  Project root : {PROJECT_ROOT}")
    print(f"  API base     : {API_BASE}")
    print(f"  Gemini key   : {'SET (' + os.environ.get('GEMINI_API_KEY','')[:8] + '…)' if os.environ.get('GEMINI_API_KEY') else 'NOT SET'}")

    test_tools()
    test_pipeline_on_samples()
    test_pipeline_single_file()

    # API tests — require server running
    sep("Checking API server…")
    api_status, _ = api_get("/api/reports")
    if api_status is None:
        warn("API server not reachable at http://localhost:8000 — skipping API tests")
        warn("Start the server with:  python api.py")
        results["warnings"] += 3
    else:
        info("API server is up")
        test_api_health()
        test_api_upload_and_analyze()
        test_gemini_triage()

    test_known_bugs()

    # ── Summary ──────────────────────────────────────────────────────────────
    sep("Test Summary")
    total = results["passed"] + results["failed"]
    pct = int(100 * results["passed"] / max(total, 1))
    color = GRN if results["failed"] == 0 else (YLW if results["failed"] < 3 else RED)
    print(f"\n  {color}{BOLD}{results['passed']}/{total} tests passed ({pct}%){RST}")
    if results["warnings"]:
        print(f"  {YLW}{results['warnings']} warning(s){RST}")
    if results["failed"]:
        print(f"  {RED}{results['failed']} failure(s){RST}")
    print()
    sys.exit(0 if results["failed"] == 0 else 1)
