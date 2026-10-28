"""Runs every test file and prints one summary. Exit code 0 = all passed.

Usage (from the project folder):   python tests/run_all.py
Needs:  pip install numpy SpeechRecognition google-genai   (no microphone or API key needed)
"""
import re
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
total_checks = 0
failed_files = []
for test in sorted(here.glob("test_*.py")):
    result = subprocess.run([sys.executable, str(test)], capture_output=True, text=True, timeout=300)
    last = [line for line in result.stdout.splitlines() if line.startswith("FAILED:")]
    summary = last[-1] if last else "no summary (crashed?)"
    count = re.search(r"\((\d+) checks\)", summary)
    total_checks += int(count.group(1)) if count else 0
    ok = result.returncode == 0
    print(f"{'PASS' if ok else 'FAIL'}  {test.name:<40} {summary.replace("FAILED: none", "no failures")}")
    if not ok:
        failed_files.append(test.name)
        print(result.stdout[-1500:], result.stderr[-1500:])
print(f"\n{total_checks} checks in {len(list(here.glob('test_*.py')))} files;",
      "ALL PASSED" if not failed_files else f"FAILED: {failed_files}")
sys.exit(1 if failed_files else 0)
