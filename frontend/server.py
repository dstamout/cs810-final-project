"""
Lightweight Flask server that serves the CS810 analysis frontend
and provides the JSON report data as an API endpoint.
"""
import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socketserver

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
FRONTEND_DIR = Path(__file__).resolve().parent


class FrontendHandler(SimpleHTTPRequestHandler):
    """Serve static files from the frontend directory and JSON reports via API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def do_GET(self):
        # API route: serve report JSON
        if self.path == "/api/report":
            self._serve_report("gemini_report.json", "baseline_report.json")
            return
        if self.path == "/api/report/baseline":
            self._serve_report("baseline_report.json")
            return
        if self.path == "/api/report/gemini":
            self._serve_report("gemini_report.json")
            return
        if self.path == "/api/reports":
            self._serve_report_list()
            return
        # Serve source file content
        if self.path.startswith("/api/source/"):
            self._serve_source()
            return
        # All other paths: serve static files
        super().do_GET()

    def _serve_report(self, *filenames):
        """Serve the first available report file."""
        for name in filenames:
            report_path = REPORTS_DIR / name
            if report_path.exists():
                data = json.loads(report_path.read_text(encoding="utf-8"))
                self._json_response(data)
                return
        self._json_response({"error": "No report found. Run the pipeline first."}, 404)

    def _serve_report_list(self):
        """List all available report files."""
        reports = []
        if REPORTS_DIR.exists():
            for f in sorted(REPORTS_DIR.glob("*.json")):
                reports.append(f.name)
        self._json_response({"reports": reports})

    def _serve_source(self):
        """Serve a source file's content for inline display."""
        rel_path = self.path.replace("/api/source/", "", 1)
        file_path = PROJECT_ROOT / rel_path
        if file_path.exists() and file_path.suffix == ".c":
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            self._json_response({"file": rel_path, "content": content})
        else:
            self._json_response({"error": f"File not found: {rel_path}"}, 404)

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        # Clean logging
        print(f"[server] {args[0]}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    with socketserver.TCPServer(("", port), FrontendHandler) as httpd:
        print(f"\n[BugHunter] CS810 Bug Scanner Dashboard")
        print(f"  -> http://localhost:{port}")
        print(f"  -> Reports dir: {REPORTS_DIR}")
        print(f"  -> Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")


if __name__ == "__main__":
    main()
