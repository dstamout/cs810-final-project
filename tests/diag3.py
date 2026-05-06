import subprocess, sys
from pathlib import Path

root = Path("c:/Users/clenc/cs810-final-project")
samples = root / "samples"
files = list(samples.rglob("*.c"))
print(f"Files: {len(files)}")

cmd = ["cppcheck", "--enable=all", "--suppress=missingIncludeSystem",
       "--template={file}:{line}:{severity}:{id}:{message}"] + [str(f) for f in files]
r = subprocess.run(cmd, capture_output=True, text=True)
print(f"RC: {r.returncode}")
print(f"STDOUT ({len(r.stdout)} chars):", repr(r.stdout[:300]))
print(f"STDERR ({len(r.stderr)} chars):", repr(r.stderr[:300]))
