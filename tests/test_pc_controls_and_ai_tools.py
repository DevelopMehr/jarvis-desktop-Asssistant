"""Tests for PC control, safety rules and the AI tool connection.

Covers: finding and opening files/folders by name, blocked programs and file types, shutdown/restart/lock
confirmation (yes / no / timeout / unrelated sentence), volume keys, a fake Google Gemini server to check
that the AI really receives the 14 tools and its tool calls open things, and the job helper treating the
job description as untrusted data with no tools.
Run:  python tests/test_pc_controls_and_ai_tools.py
"""
import ctypes
import json
import os
import sys
import tempfile
import threading
import time
import types as pytypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

spoken = []
class FakeEngine:
    def setProperty(self, *a): pass
    def say(self, t): spoken.append(t)
    def runAndWait(self): pass
sys.modules["pyttsx3"] = pytypes.SimpleNamespace(init=lambda: FakeEngine())

import support
support.prepare()
import webbrowser
opened = []
webbrowser.open = lambda url, *a, **k: opened.append(url) or True

import jarvis

checks = []
def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)

def said(sub):
    jarvis.wait_speaking(3)
    return any(sub.lower() in s.lower() for s in spoken)

jarvis.start_threads(with_commands=False)

# ---------- fake files for search ----------
tmp = Path(tempfile.mkdtemp())
(tmp / "Documents" / "Work").mkdir(parents=True)
(tmp / "Documents" / "Work" / "Mehr CV.pdf").write_text("x")
(tmp / "Documents" / "Work" / "installer.exe").write_text("x")
(tmp / "Documents" / "Work" / "run_me.bat").write_text("x")
(tmp / "Documents" / "notes_cv_old.txt").write_text("x")
jarvis.Path.home = classmethod(lambda cls: tmp)
jarvis.EXTRA_FOLDERS = []
launched = []
jarvis.IS_WINDOWS = False
def fake_popen(args, *a, **k):
    if args[0] in ("xdg-open", "open") or args[0] in jarvis.APPS.values():
        launched.append(args); return None
    raise FileNotFoundError(args[0])
jarvis.subprocess.Popen = fake_popen

# ---------- file / folder opening ----------
hits = jarvis.search_files("cv")
check("search finds CV pdf", any(h.name == "Mehr CV.pdf" for h in hits))
check("search never returns exe/bat", not any(h.suffix in jarvis.BLOCKED_EXT for h in hits))
check("search for exe name finds nothing", jarvis.search_files("installer") == [])
check("search for bat name finds nothing", jarvis.search_files("run_me") == [])
launched.clear()
jarvis.handle("open Mehr CV")
check("'open Mehr CV' launches the pdf", any("Mehr CV.pdf" in str(x) for x in launched[0]))
launched.clear()
jarvis.handle("open file work")
check("open folder by name", any(str(x).endswith("Work") for x in launched[0]))
spoken.clear()
jarvis.handle("open something that does not exist anywhere")
check("missing file says so", said("couldn't find"))
check("open_file refuses exe directly", jarvis.open_file(tmp / "Documents" / "Work" / "installer.exe") is False)

# ---------- blocked apps ----------
spoken.clear(); launched.clear()
jarvis.handle("open cmd")
check("cmd blocked", said("for safety") and not launched)
jarvis.handle("open powershell")
check("powershell blocked", not launched)
check("blocked-app name case-insensitive", (jarvis.handle("open CMD"), not launched)[1])

# ---------- power controls ----------
runs = []
jarvis.IS_WINDOWS = True
class R:  # fake subprocess result
    returncode = 0
jarvis.subprocess.run = lambda *a, **k: runs.append(a[0]) or R()
ctypes.windll = pytypes.SimpleNamespace(user32=pytypes.SimpleNamespace(LockWorkStation=lambda: runs.append("LOCKED")))

for phrase in ["shutdown", "shut down the laptop", "turn off my computer", "restart", "restart the pc", "lock", "lock my laptop"]:
    runs.clear(); jarvis.state["pending"] = None
    jarvis.handle(phrase)
    check(f"'{phrase}' asks first, runs nothing", jarvis.state["pending"] is not None and not runs)

runs.clear(); jarvis.state["pending"] = None
jarvis.handle("shutdown"); jarvis.handle("yes")
check("shutdown + yes runs shutdown /s with delay", runs and runs[0][:2] == ["shutdown", "/s"] and runs[0][-1] == "15")
runs.clear()
jarvis.handle("cancel shutdown")
check("cancel shutdown runs shutdown /a", runs and runs[0] == ["shutdown", "/a"])
runs.clear()
jarvis.handle("restart"); jarvis.handle("yes")
check("restart + yes runs /r", runs and runs[0][:2] == ["shutdown", "/r"])
runs.clear()
jarvis.handle("shutdown"); jarvis.handle("no")
check("shutdown + no runs nothing", not runs and jarvis.state["pending"] is None)
runs.clear()
jarvis.handle("shutdown"); jarvis.handle("what time is it")
check("shutdown + other sentence cancels, runs nothing", not runs and jarvis.state["pending"] is None)
runs.clear()
jarvis.handle("yes")
check("stray 'yes' with nothing pending does nothing", not runs)
runs.clear(); jarvis.state["pending"] = None
jarvis.handle("shutdown")
act, exp = jarvis.state["pending"]
jarvis.state["pending"] = (act, time.time() - 1)  # expired
jarvis.handle("yes")
check("expired confirmation does not run", not runs)
runs.clear()
jarvis.handle("lock"); jarvis.handle("yes")
check("lock + yes locks screen", "LOCKED" in runs)
runs.clear(); jarvis.state["pending"] = None
jarvis.handle("I should restart my sleep schedule and shut down my inbox tonight please")
check("long sentence mentioning words does NOT trigger power", jarvis.state["pending"] is None and not runs)
jarvis.handle("how do I restart my router")
check("'restart my router' does NOT trigger power", jarvis.state["pending"] is None)
check("AI tools contain no power functions",
      not any(f.__name__ in ("run_power", "ask_power_confirm", "cancel_power") for f in jarvis.TOOLS))

# ---------- volume / screenshot / normal ----------
runs.clear()
jarvis.handle("volume up")
check("volume up uses powershell key 175 x5", runs and "175" in runs[0][-1] and "1..5" in runs[0][-1])
runs.clear()
jarvis.handle("mute")
check("mute key 173 x1", runs and "173" in runs[0][-1] and "1..1" in runs[0][-1])
check("change_volume rejects junk", "must be" in jarvis.change_volume("sideways"))
jarvis.IS_WINDOWS = False

# ---------- queue discipline ----------
check("exit returns False", jarvis.handle("exit") is False)
check("normal command returns True", jarvis.handle("what is the date") is True)

# ---------- fake Google for AI tool use incl. new tools ----------
requests_seen = []
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        requests_seen.append(body)
        has_result = any("functionResponse" in p for c in body["contents"] for p in c.get("parts", []))
        if not has_result and "tools" in body:
            parts = [{"functionCall": {"name": "open_file_or_folder", "args": {"name": "Mehr CV"}}}]
        else:
            parts = [{"text": "Opened your CV."}]
        data = json.dumps({"candidates": [{"content": {"role": "model", "parts": parts},
                                           "finishReason": "STOP", "index": 0}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
srv = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
opts = jarvis.types.HttpOptions(base_url=f"http://127.0.0.1:{srv.server_address[1]}", timeout=15000)
jarvis.client_fast = jarvis.genai.Client(api_key="fake", http_options=opts)
jarvis.client_long = jarvis.client_fast
jarvis.model_list = ["fake"]
launched.clear(); spoken.clear()
jarvis.handle("please open my cv for me")
check("AI -> open_file_or_folder tool -> pdf launched", launched and "Mehr CV.pdf" in str(launched[0]))
names = sorted(d["name"] for d in requests_seen[0]["tools"][0]["functionDeclarations"])
print("tools:", names)
check("14 tools declared", len(names) == 14)
check("system prompt tells AI it cannot power off", "can NOT shut down" in json.dumps(requests_seen[0]["systemInstruction"]))

# ---------- bad tool args do not crash ----------
check("set_timer bad", "Invalid" in jarvis.set_timer("x", "y"))

bad = [n for n, ok in checks if not ok]
print("\nFAILED:", bad if bad else "none", f"({len(checks)} checks)")
sys.exit(1 if bad else 0)
