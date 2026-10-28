"""Tests for the local command understanding (no AI needed).

Covers: "open youtube and search X and play it", "play X", "go on linkedin and search ... jobs in ...",
sites like Indeed/GitHub/DAAD, pause/next, many ways of phrasing and mis-hearing ("you tube",
"linked in", "can you please..."), sentences that must NOT be hijacked, and the YouTube page reader
(including network failure and fallback).
Run:  python tests/test_smart_commands.py
"""
import sys
import types as pytypes
import urllib.parse as up

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

jarvis.start_threads(with_commands=False)
checks = []
def check(name, cond, extra=""):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"   -> {extra}" if not cond else ""))

# --- fake YouTube: lookup returns a known video ---
lookups = []
def fake_find(q):
    lookups.append(q)
    return "VID12345678", "Fake Title"
orig_find = jarvis.find_youtube_video
jarvis.find_youtube_video = fake_find

def run(utterance):
    opened.clear(); lookups.clear(); spoken.clear()
    jarvis.handle(utterance)
    jarvis.wait_speaking(2)
    return list(opened), list(lookups)

PLAY = "https://www.youtube.com/watch?v=VID12345678&autoplay=1"

# ---------- YouTube: must PLAY ----------
for utt, expect_q in [
    ("open youtube and search tum hi ho and play it", "tum hi ho"),
    ("Open YouTube and search for Tum Hi Ho and play it.", "tum hi ho"),
    ("open you tube and search kesariya and play it", "kesariya"),
    ("can you please open youtube and play kesariya", "kesariya"),
    ("go on youtube and search shape of you and play that", "shape of you"),
    ("go to youtube, search blinding lights, then play the first one", "blinding lights"),
    ("open youtube then search believer and play it please", "believer"),
    ("I want you to open youtube and play on my way", "on my way"),
    ("play shape of you", "shape of you"),
    ("play shape of you on youtube", "shape of you"),
    ("hey jarvis play blinding lights", "blinding lights"),
    ("could you play perfect by ed sheeran for me", "perfect by ed sheeran"),
    ("youtube play believer", "believer"),
    ("search arijit singh songs on youtube and play the first one", "arijit singh songs"),
    ("play tum hi ho on yt", "tum hi ho"),
]:
    o, l = run(utt)
    check(f"PLAY: {utt!r}", o == [PLAY] and l == [expect_q], f"opened={o} lookups={l}")

# ---------- YouTube: search only (no play) ----------
for utt, q in [("go on youtube and search lofi music", "lofi%20music"),
               ("youtube lofi beats", "lofi%20beats"),
               ("open youtube and look up python tutorial", "python%20tutorial")]:
    o, l = run(utt)
    check(f"SEARCH-ONLY: {utt!r}", len(o) == 1 and "results?search_query=" + q in o[0] and not l, f"{o} {l}")

# ---------- open site only ----------
for utt, url in [("open youtube", "https://www.youtube.com"), ("go on youtube", "https://www.youtube.com"),
                 ("open you tube", "https://www.youtube.com"), ("youtube", "https://www.youtube.com"),
                 ("please open the youtube website", "https://www.youtube.com"),
                 ("go to linkedin", "https://www.linkedin.com"), ("open linked in", "https://www.linkedin.com"),
                 ("open gmail", "https://mail.google.com"), ("go to g mail", "https://mail.google.com"),
                 ("open github", "https://github.com"), ("launch upwork", "https://www.upwork.com")]:
    o, l = run(utt)
    check(f"OPEN: {utt!r}", o == [url], str(o))

# ---------- LinkedIn ----------
def li(utt, must_have, must_not=()):
    o, _ = run(utt)
    ok = len(o) == 1 and all(m in o[0] for m in must_have) and not any(m in o[0] for m in must_not)
    check(f"LINKEDIN: {utt!r}", ok, str(o))
    return o

li("go on linkedin and search machine learning engineer jobs in germany",
   ["linkedin.com/jobs/search/", "keywords=machine%20learning%20engineer", "location=germany"])
li("open linkedin and find data scientist jobs", ["/jobs/search/", "keywords=data%20scientist"], ["location="])
li("go to linked in and search for ai engineer jobs in berlin", ["/jobs/search/", "keywords=ai%20engineer", "location=berlin"])
li("search remote python developer jobs on linkedin", ["/jobs/search/", "f_WT=2", "python%20developer"])
li("find jobs in germany on linkedin", ["/jobs/search/", "location=germany"])
li("find me a job on linkedin", ["/jobs/search/", "keywords=job"])
li("search for john smith on linkedin", ["/search/results/all/", "keywords=john%20smith"], ["/jobs/"])
li("open linkedin and search internships for ai students", ["/jobs/search/", "keywords=ai%20students"], ["location="])
li("linkedin machine learning jobs", ["/jobs/search/", "keywords=machine%20learning"])

# ---------- other sites ----------
o, _ = run("open indeed and search data analyst"); check("INDEED open+search", o == ["https://www.indeed.com/jobs?q=data%20analyst"], str(o))
o, _ = run("search ml engineer on indeed"); check("INDEED search-on", "indeed.com/jobs?q=ml%20engineer" in o[0], str(o))
o, _ = run("search scholarships in germany on daad"); check("DAAD via google site:", "site%3Adaad.de" in o[0], str(o))
o, _ = run("find fastapi tutorial on github"); check("GITHUB search", "github.com/search?q=fastapi%20tutorial" in o[0], str(o))
o, _ = run("search web designer on upwork"); check("UPWORK search", "upwork.com" in o[0] and "web%20designer" in o[0], str(o))

# ---------- media keys ----------
cmds = []
class R: returncode = 0
jarvis.IS_WINDOWS = True
jarvis.subprocess.run = lambda *a, **k: cmds.append(a[0][-1]) or R()
for utt, code in [("pause", "179"), ("resume", "179"), ("play", "179"), ("pause the music", "179"),
                  ("next song", "176"), ("skip", "176"), ("previous song", "177"),
                  ("play it", "179"), ("play music", "179"), ("stop the music", "179")]:
    cmds.clear()
    jarvis.handle(utt)
    check(f"MEDIA: {utt!r}", len(cmds) == 1 and f"[char]{code}" in cmds[0], str(cmds))
jarvis.IS_WINDOWS = False

# ---------- must NOT be hijacked (should go on to the normal path / AI) ----------
for utt in ["write a cover letter for me", "what is machine learning", "open notepad", "open Mehr CV",
            "search python tutorials", "explain how youtube recommends videos",
            "remember that i like to play chess", "note play football at 5", "timer 5",
            "how do I get a job at google", "tell me about linkedin"]:
    check(f"NOT-SMART: {utt!r}", jarvis.smart_command(utt.lower()) is False)
check("'stop' no longer quits Jarvis", jarvis.handle("stop") is True)
check("'exit' still quits", jarvis.handle("exit") is False)

# ---------- YouTube page parsing ----------
html = ('..."contents":[{"adSlotRenderer":{"videoId":"ADADADADADA"}},'
        '{"videoRenderer":{"videoId":"dQw4w9WgXcQ","thumbnail":{"thumbnails":[{"url":"x"}]},'
        '"title":{"runs":[{"text":"Tum Hi Ho \\u2013 Official \\"Video\\""}],"accessibility":{}},'
        '"longBylineText":{"runs":[{"text":"Artist"}]}}},{"videoRenderer":{"videoId":"SECONDVIDEO"}}]...')
vid, title = jarvis.parse_youtube_results(html)
check("parse: first real video id (skips ad)", vid == "dQw4w9WgXcQ", str(vid))
check("parse: title decoded", title == 'Tum Hi Ho – Official "Video"', str(title))
check("parse: empty page -> None", jarvis.parse_youtube_results("<html>nothing</html>") == (None, None))

# ---------- the REAL lookup function, with a fake network layer ----------
jarvis.find_youtube_video = orig_find
class FakeResp:
    def __init__(self, text): self.text = text
    def read(self): return self.text.encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False

urls_called = []
def fake_urlopen_ok(req, timeout=0):
    urls_called.append(req.full_url)
    return FakeResp(html)
jarvis.urllib.request.urlopen = fake_urlopen_ok
check("real lookup returns id+title", orig_find("tum hi ho") == ("dQw4w9WgXcQ", 'Tum Hi Ho – Official "Video"'))
check("real lookup asks videos-only first", "sp=EgIQAQ%3D%3D" in urls_called[0] and "tum%20hi%20ho" in urls_called[0])

calls = []
def fake_urlopen_second(req, timeout=0):
    calls.append(req.full_url)
    return FakeResp("<html>no videos</html>" if len(calls) == 1 else html)
jarvis.urllib.request.urlopen = fake_urlopen_second
check("falls back to unfiltered search when filtered page is empty",
      orig_find("x")[0] == "dQw4w9WgXcQ" and len(calls) == 2)

def fake_urlopen_down(req, timeout=0):
    raise OSError("network down")
jarvis.urllib.request.urlopen = fake_urlopen_down
check("network failure -> (None, None), no crash", orig_find("x") == (None, None))

opened.clear(); spoken.clear()
jarvis.handle("open youtube and search tum hi ho and play it")
jarvis.wait_speaking(2)
check("lookup fails -> still opens YouTube results", len(opened) == 1 and "results?search_query=tum%20hi%20ho" in opened[0], str(opened))
check("lookup fails -> honest message", any("couldn't start it automatically" in s for s in spoken), str(spoken))

opened.clear(); spoken.clear()
jarvis.urllib.request.urlopen = fake_urlopen_ok
jarvis.handle("play tum hi ho")
jarvis.wait_speaking(2)
check("success -> opens the video page", opened == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&autoplay=1"], str(opened))
check("success -> says the real title", any("Tum Hi Ho" in s for s in spoken), str(spoken))

bad = [n for n, ok in checks if not ok]
print(f"\nFAILED: {bad if bad else 'none'}  ({len(checks)} checks)")
sys.exit(1 if bad else 0)
