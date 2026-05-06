import sys
sys.path.insert(0, 'src')
from pipeline import discover_c_files, run_cppcheck, parse_cppcheck_output, run_clang_analyzer, parse_clang_output, match_findings
from pathlib import Path

files = discover_c_files(Path('samples'))
print(f"Discovered {len(files)} files: {[f.name for f in files]}")

cpp_raw = run_cppcheck(files)
clang_raw = run_clang_analyzer(files)

cpp = parse_cppcheck_output(cpp_raw)
clang = parse_clang_output(clang_raw)

print(f"Cppcheck parsed: {len(cpp)} findings")
for f in cpp[:5]:
    print(f"  [{f.severity}] {f.category} in {Path(f.file).name}:{f.line}")

print(f"Clang parsed: {len(clang)} findings")
for f in clang[:5]:
    print(f"  [{f.severity}] {f.category} in {Path(f.file).name}:{f.line}")

fused = match_findings(cpp, clang)
print(f"\nCritical candidates: {len(fused['critical_candidates'])}")
for c in fused["critical_candidates"]:
    print(f"  MATCH: {Path(c['cppcheck']['file']).name}:{c['cppcheck']['line']} {c['cppcheck']['category']} <-> {c['clang']['category']}")
