import json
import os
import shutil
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "reports"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

# Clear previous session data on startup for a clean slate
if REPORTS_DIR.exists():
    shutil.rmtree(REPORTS_DIR)
if UPLOADS_DIR.exists():
    shutil.rmtree(UPLOADS_DIR)

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/reports")
def get_reports():
    reports = []
    if REPORTS_DIR.exists():
        for f in sorted(REPORTS_DIR.glob("*.json")):
            reports.append(f.name)
    return {"reports": reports}

@app.get("/api/report/{report_name}")
def get_report(report_name: str):
    report_path = REPORTS_DIR / report_name
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Report not found")

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    
    saved_files = []
    valid_exts = (".c", ".cpp", ".cc", ".cxx", ".h", ".hpp")
    for file in files:
        if file.filename.lower().endswith(valid_exts):
            file_path = session_dir / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(file.filename)
            
    if not saved_files:
        raise HTTPException(status_code=400, detail="No valid C/C++ files uploaded")
        
    return {"session_id": session_id, "files": saved_files}

class AnalyzeRequest(BaseModel):
    session_id: str
    use_gemini: bool = False

@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    session_dir = UPLOADS_DIR / request.session_id
    if not session_dir.exists():
        raise HTTPException(status_code=404, detail="Session not found")
        
    report_name = f"report_{request.session_id}.json"
    report_path = REPORTS_DIR / report_name
    
    cmd = [
        "python", str(PROJECT_ROOT / "src" / "pipeline.py"),
        "--input", str(session_dir),
        "--output", str(report_path)
    ]
    
    if request.use_gemini:
        cmd.append("--use-gemini")
        
    try:
        # Run pipeline synchronously for simplicity in this demo
        env = os.environ.copy()
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return {"error": result.stderr}
            
        return {"report": report_name, "logs": result.stdout}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/source/{session_id}/{filename}")
def get_source(session_id: str, filename: str):
    # Try uploads first
    file_path = UPLOADS_DIR / session_id / filename
    if not file_path.exists():
        # Fallback to samples
        file_path = PROJECT_ROOT / "samples" / filename
        
    if file_path.exists():
        return {"file": filename, "content": file_path.read_text(encoding="utf-8", errors="ignore")}
    raise HTTPException(status_code=404, detail="File not found")

# Serve React App
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except (StarletteHTTPException, FileNotFoundError):
            return FileResponse(FRONTEND_DIST / "index.html")

if FRONTEND_DIST.exists():
    app.mount("/", SPAStaticFiles(directory=FRONTEND_DIST, html=True), name="spa")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
