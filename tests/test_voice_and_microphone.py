"""Tests for the voice input, using a simulated microphone.

Covers: quiet microphone, noisy room, silence, speaking the instant listening starts, long speech cut-off,
the reasons for "heard nothing", mic test verdicts, hands-free end to end, hands-free ON by default at
start-up, saved settings, and clear messages when voice libraries are missing.
Run:  python tests/test_voice_and_microphone.py
"""
import json
import queue
import sys
import threading
import time
import types as pytypes

import numpy as np

spoken = []
class FakeEngine:
    def setProperty(self, *a): pass
    def say(self, t): spoken.append(t)
    def runAndWait(self): pass
sys.modules["pyttsx3"] = pytypes.SimpleNamespace(init=lambda: FakeEngine())

# ---------- fake microphone ----------
SCRIPTS = []   # each InputStream opened takes the next script: a list of loudness values per 0.2 s block
class FakeStream:
    def __init__(self, script): self.script = list(script)
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self, n):
        amp = self.script.pop(0) if self.script else 20
        return (np.random.randn(n, 1) * amp).clip(-32000, 32000).astype(np.int16), False
def InputStream(**kw):
    return FakeStream(SCRIPTS.pop(0) if SCRIPTS else [])
sys.modules["sounddevice"] = pytypes.SimpleNamespace(
    InputStream=InputStream, query_devices=lambda kind=None: {"name": "Fake Mic"})

import support
support.prepare()
import webbrowser
opened = []
webbrowser.open = lambda url, *a, **k: opened.append(url) or True
import jarvis
assert jarvis.VOICE_OK, jarvis.VOICE_ERROR
jarvis.SETTINGS_FILE.unlink(missing_ok=True)

checks = []
def check(name, cond, extra=""):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"   -> {extra}" if not cond else ""))

B = 6400  # bytes per 0.2 s block

# ---------- microphone sensitivity ----------
SCRIPTS[:] = [[20]*3 + [250]*12 + [20]*12]
raw, _ = jarvis.record_until_silence()
check("QUIET mic (speech level 250) is heard", raw is not None and 14*B <= len(raw) <= 26*B, f"{None if raw is None else len(raw)/B}")

SCRIPTS[:] = [[20]*100]
raw, _ = jarvis.record_until_silence(max_wait=2.0)
check("silence -> nothing recorded", raw is None)

SCRIPTS[:] = [[100]*100]
raw, _ = jarvis.record_until_silence(max_wait=2.0)
check("steady noise (100) is NOT mistaken for speech", raw is None)

SCRIPTS[:] = [[100]*3 + [600]*10 + [100]*12]
raw, _ = jarvis.record_until_silence()
check("speech over noisy room is heard", raw is not None and len(raw) > 10*B)

SCRIPTS[:] = [[800]*20 + [20]*12]
raw, _ = jarvis.record_until_silence()
check("you start talking the instant it listens", raw is not None and len(raw) > 10*B)

SCRIPTS[:] = [[20]*3 + [250]*50]
t0 = time.time()
raw, _ = jarvis.record_until_silence(max_len=2.0)
check("long speech is cut at max_len", raw is not None and len(raw) < 20*B)

# ---------- listen_voice reasons ----------
sr = jarvis.sr
jarvis.sr.Recognizer.recognize_google = lambda self, audio, **k: "open youtube"
SCRIPTS[:] = [[20]*3 + [400]*8 + [20]*12]
check("listen_voice returns the recognised text", jarvis.listen_voice() == "open youtube")

SCRIPTS[:] = [[20]*100]
check("silence -> '' with reason silence", jarvis.listen_voice() == "" and jarvis.listen_info["reason"] == "silence")

def raise_unknown(self, audio, **k): raise sr.UnknownValueError()
jarvis.sr.Recognizer.recognize_google = raise_unknown
SCRIPTS[:] = [[20]*3 + [400]*8 + [20]*12]
check("unintelligible -> reason unclear", jarvis.listen_voice() == "" and jarvis.listen_info["reason"] == "unclear")

def raise_req(self, audio, **k): raise sr.RequestError("no internet")
jarvis.sr.Recognizer.recognize_google = raise_req
SCRIPTS[:] = [[20]*3 + [400]*8 + [20]*12]
check("no internet -> reason error", jarvis.listen_voice() == "" and jarvis.listen_info["reason"] == "error")

# ---------- microphone test ----------
jarvis.sr.Recognizer.recognize_google = lambda self, audio, **k: "open youtube"
for amp, word in [(500, "working"), (150, "quiet"), (30, "almost nothing")]:
    SCRIPTS[:] = [[amp]*10]
    out = jarvis.mic_test(seconds=1)
    check(f"mic_test at level {amp} says '{word}'", word in out and "Fake Mic" in out, out)

# ---------- hands-free end to end ----------
jarvis.start_threads(with_commands=True)
jarvis.find_youtube_video = lambda q: ("abcdefghijk", "Test Song")
jarvis.state["voice"] = True
SCRIPTS[:] = [[20]*3 + [400]*8 + [20]*12]
opened.clear()
threading.Thread(target=jarvis.listen_loop, daemon=True).start()
for _ in range(100):
    if opened: break
    time.sleep(0.1)
check("HANDS-FREE: spoken sentence is heard and the command runs", opened == ["https://www.youtube.com"], str(opened))
jarvis.state["voice"] = False
for _ in range(100):
    if not jarvis.listener_running.is_set(): break
    time.sleep(0.1)
check("hands-free loop stops when switched off", not jarvis.listener_running.is_set())

# ---------- first run: hands-free ON by default, readiness shown ----------
jarvis.GUI_MODE = True
while not jarvis.ui_queue.empty(): jarvis.ui_queue.get_nowait()
jarvis.SETTINGS_FILE.unlink(missing_ok=True)
jarvis.start_brain = lambda: None
jarvis.state["voice"] = False
jarvis.boot()
items = []
while not jarvis.ui_queue.empty(): items.append(jarvis.ui_queue.get_nowait())
texts = " ".join(i[2] for i in items if i[0] == "msg")
check("BOOT: hands-free is ON by default", jarvis.state["voice"] is True)
check("BOOT: window is told to start listening", ("voice_changed",) in items)
check("BOOT: shows microphone name", "Voice input: ready (microphone: Fake Mic)" in texts, texts)
check("BOOT: shows hands-free ON", "Hands-free listening: ON" in texts)
jarvis.wait_speaking(3)
check("BOOT: greeting (shown and spoken) says it is listening", any("I'm listening" in i[2] for i in items if i[0]=="msg") and any("I'm listening" in s for s in spoken), str(spoken[-3:]))
jarvis.state["voice"] = False  # stop any loop the boot message started

# ---------- settings persistence ----------
jarvis.state["voice"] = False; jarvis.state["speak"] = False
jarvis.save_settings()
jarvis.state["voice"] = True; jarvis.state["speak"] = True
jarvis.load_settings()
check("settings remember hands-free OFF and speak OFF", jarvis.state["voice"] is False and jarvis.state["speak"] is False)
jarvis.SETTINGS_FILE.unlink(missing_ok=True)
jarvis.load_settings()
check("no settings file -> hands-free ON, speak ON", jarvis.state["voice"] is True and jarvis.state["speak"] is True)
jarvis.state["voice"] = False

# ---------- commands ----------
jarvis.state["speak"] = True
jarvis.handle("voice on"); check("'voice on' turns it on and saves", jarvis.state["voice"] is True and json.loads(jarvis.SETTINGS_FILE.read_text())["hands_free"] is True)
jarvis.handle("stop listening"); check("'stop listening' turns it off", jarvis.state["voice"] is False)
for _ in range(100):
    if not jarvis.listener_running.is_set(): break
    time.sleep(0.1)
check("'stop' is not an exit word", jarvis.handle("stop") is True)

while not jarvis.ui_queue.empty(): jarvis.ui_queue.get_nowait()
jarvis.state["voice"] = True
SCRIPTS[:] = [[500]*30]
jarvis.handle("mic test")
items = []
while not jarvis.ui_queue.empty(): items.append(jarvis.ui_queue.get_nowait())
texts = " ".join(i[2] for i in items if i[0] == "msg")
check("'mic test' command reports", "Your microphone is working" in texts, texts)
check("'mic test' restores hands-free afterwards", jarvis.state["voice"] is True and ("voice_changed",) in items)
jarvis.state["voice"] = False
for _ in range(100):
    if not jarvis.listener_running.is_set(): break
    time.sleep(0.1)

while not jarvis.ui_queue.empty(): jarvis.ui_queue.get_nowait()
jarvis.handle("status")
items = []
while not jarvis.ui_queue.empty(): items.append(jarvis.ui_queue.get_nowait())
check("'status' shows a report", any(i[0] == "msg" and "Voice input:" in i[2] for i in items))

# ---------- voice libraries missing: honest, visible message ----------
jarvis.VOICE_OK = False
jarvis.VOICE_ERROR = "PortAudio library not found"
check("report explains WHY voice is off", "PortAudio library not found" in jarvis.readiness_report())
spoken.clear(); jarvis.handle("voice on"); jarvis.wait_speaking(2)
check("'voice on' without libraries explains why", any("PortAudio" in s for s in spoken), str(spoken))
check("mic_test without libraries explains why", "PortAudio" in jarvis.mic_test())
jarvis.VOICE_OK = True

jarvis.SETTINGS_FILE.unlink(missing_ok=True)
bad = [n for n, ok in checks if not ok]
print(f"\nFAILED: {bad if bad else 'none'}  ({len(checks)} checks)")
sys.exit(1 if bad else 0)
