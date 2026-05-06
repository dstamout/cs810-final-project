import subprocess, sys, json, tempfile
from pathlib import Path

root = Path("c:/Users/clenc/cs810-final-project")
samples = root / "samples"
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "r.json"
    cmd = [sys.executable, str(root / "src" / "pipeline.py"),
           "--input", str(samples), "--output", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print("RC:", r.returncode)
    print("STDOUT:", r.stdout[:500])
    print("STDERR:", r.stderr[:500])
    if out.exists():
        data = json.loads(out.read_text())
        print("Meta:", data["meta"])
