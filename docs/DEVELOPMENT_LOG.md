# Development log

The step-by-step history of how Jarvis was built, including everything that broke. It was built over a few days in October 2026 with Claude (Anthropic) as an AI pair-programmer: **I** set the goals, ran each version on my own Windows laptop and reported the real results and errors; **the AI** wrote and revised the code and tests.

Each step uses the same format: **Goal → What happened → Cause → Fix → Result**.

---

## Step 0 — The goal and the plan

**Goal (my words, summarised):** a Tony-Stark-style professional assistant that works by voice and text, knows my background so it can help with job applications without making things up, searches YouTube and Google, controls my laptop, and runs like real software.

**Decision:** build it in stages instead of all at once, so each layer can be tested on my laptop before adding the next:

1. Ears and mouth: listen (voice or text) and speak.
2. Hands: open websites, search Google and YouTube, open apps.
3. Brain: an AI model that answers using my profile.
4. Job helper: cover letters and interview preparation from a job description.
5. Memory: remember things between sessions.

**Decision (mine):** the project lives in a folder on my D: drive (`D:\Projects\AI Projects\Jarvis`).

---

## Step 1 — Ears, mouth and hands (first version)

**Built:** a single `jarvis.py` with `pyttsx3` for speaking, `SpeechRecognition` for voice input, and fixed commands: time, date, `search <x>`, `youtube <x>`, `open <site or app>`.

**Result:** it ran on my laptop and spoke, but the microphone failed (next step).

---

## Step 2 — The PyAudio problem

**What happened:** `pip install pyaudio` ended with `Failed building wheel for pyaudio`. Running Jarvis printed `Mic problem: pyaudio could not find`.

**Cause:** `pip` tried to build PyAudio from source, which needs a C compiler that my laptop does not have. Nothing else was broken — text mode and the voice output already worked.

**Fix:** replaced PyAudio with `sounddevice` (installs without a compiler) plus `numpy`. The recording is wrapped in `speech_recognition.AudioData` and sent to the same recogniser. At this stage it recorded a fixed 6 seconds.

**Result:** voice input worked on my laptop.

---

## Step 3 — Adding the AI brain (Gemini)

**Built:** anything that is not a fixed command goes to Google's Gemini API. My background is read from `profile.txt` and given to the model as instructions: *be direct, use only facts from the profile, ask instead of inventing.*

**What I did:** created a free API key in Google AI Studio and saved it in `api_key.txt` (the program reads it from that file, so the key never appears in the code).

**Lesson learned:** at one point a key was pasted into a chat window. A key that has been pasted anywhere outside its file must be treated as exposed — delete it and create a new one. This is why the README stresses `.gitignore` and keeping the key only in `api_key.txt`.

**Result:** `Brain connected.` appeared on my laptop.

---

## Step 4 — Four bugs between "connected" and "working"

### 4a. `Cannot send a request, as the client has been closed`
- **Cause:** the Gemini client was created as a *local variable* inside `start_brain()`. When the function finished, Python cleaned it up and closed it.
- **Fix:** keep the client in a module-level (global) variable.

### 4b. `404 NOT_FOUND … This model models/gemini-2.5-flash is no longer available to new users`
- **Cause:** the model name was written into the code, and Google had retired it for new accounts.
- **Fix:** use the model name Google's error message recommended (`gemini-3.8-flash`), then go further: at start-up ask Google which Flash models my key can use (`client.models.list()`), put the preferred one first and keep a few more as fallbacks. The model name is now one constant at the top of the file.

### 4c. `503 UNAVAILABLE … This model is currently experiencing high demand`
- **Cause:** Google's servers were overloaded. Not my key and not my code, but my code had no plan for it.
- **Fix:** first attempt retried with waiting; I found the waiting too slow, so Jarvis now **skips immediately to the next model**, and remembers which model last answered so it is tried first next time.

### 4d. Stuck on "Thinking…" forever
- **Cause:** the network request had no time limit, so if Google never answered, Jarvis waited forever.
- **Fix:** request timeouts, first 30 seconds then 15 seconds for normal questions. A stuck model is skipped like a failing one.

**Result:** questions were answered reliably. I confirmed by hand that typed commands opened the browser and the AI replied.

---

## Step 5 — "Make it complete and professional" (version 2)

**What I asked for:** everything working together — voice and text, controlling my laptop, job applications, memory — not separate scripts.

**Added:**

- **Tool (function) calling:** the AI can now *act*, not just talk, by calling a fixed list of tools: open a website, Google search, YouTube search, open an allowed app, save and read notes, set a timer, read the time.
- **Persistent memory:** `remember <fact>`, plus the recent conversation, saved in `memory.json`. Text that looks like a password, card number or secret is refused.
- **Job helper:** I paste a job description into `job.txt`; Jarvis writes an honest fit summary (including gaps), a cover letter, likely interview questions with answer outlines, and what to add to my profile. The job description is treated as **untrusted data**, and the AI gets **no tools** while analysing it.
- **Smarter voice recording:** recording stops when I stop talking instead of after a fixed 6 seconds.
- **Notes and timers, logging to `jarvis.log`, long answers saved to an `outputs/` folder** with only the start spoken aloud.

**How it was verified:** the code was tested against a **fake Gemini server** that pretends to be Google and asks Jarvis to call a tool, which proves the whole tool-calling path works end to end without needing a real API key in the test.

---

## Step 6 — PC control, a real window, and safety (version 3)

**What I asked for:** can it open any file, shut down, and look professional — without opening VS Code every time?

**Design decision:** shutting down by voice is useful but dangerous (a misheard word could turn my laptop off), so it must always ask first.

**Added:**

- **A Tkinter window** (dark theme, status light, quick buttons, command history).
- **Threads and queues** so speaking, listening and network calls never freeze the window (see "Threads and queues" in the README).
- **Open files and folders by name** (searches Desktop, Documents, Downloads and my project folder), **volume**, **screenshots**.
- **Lock / restart / shutdown with confirmation:** Jarvis asks "are you sure?", waits 20 seconds for a "yes", and runs shutdown/restart with a 15-second delay so it can be cancelled with `cancel shutdown`. The AI has **no tool** for these.
- **Safety blocklists:** command prompt, PowerShell, registry editor and similar are never opened; neither are runnable file types (`.exe`, `.bat`, `.ps1`, …).

---

## Step 7 — "It says I can't" (the YouTube and LinkedIn fix)

**What happened (my report):** *"When I say open YouTube and search this song and play it, it says I can't. When I say just open YouTube, sometimes it says I can't do this right now, try again later."*

**Cause (found by analysing the flow):**

1. These sentences were handled by the AI, which had a *search* tool but nothing that could *play*, so it answered "I can't".
2. Sometimes the AI service was busy, so even simple requests failed with "try again later".

**Fix:** the AI must not be the first step for things that can be understood with simple rules. Added a **local command parser** (regular expressions) that runs before the AI:

- understands filler and variations ("can you please…", "go on…", "you tube", "linked in");
- `play <song>` / "open youtube and search X and play it" → reads YouTube's results page for the first real video and opens it;
- "go on linkedin and search <job> jobs in <place>" → builds a LinkedIn **jobs** search URL with keywords, location and remote filter (I do the applying myself);
- the same for Indeed, Upwork, Fiverr, GitHub, DAAD and more;
- pause / resume / next / previous using the Windows media keys.

The AI also got matching tools (`play_on_youtube`, `search_on_site`, `media_control`) and a rule never to say it "cannot" do what its tools can do.

**Verified by:** 77 automated checks of the phrasings above, including mis-hearings and sentences that must *not* be hijacked, plus a test of the YouTube page reader and of what happens when the network is down.

---

## Step 8 — Making it a desktop app

**What I asked for:** an icon on the desktop; no VS Code.

**Built:** `install_jarvis.py` (run through `Install Jarvis.bat`) installs the libraries and creates Desktop and Start-menu shortcuts that start Jarvis with `pythonw` (no console window), with a custom icon. Optionally it starts with Windows. When there is no console, Python's output streams are replaced so libraries do not crash trying to print.

**Result:** the icon appeared on my Desktop and the Jarvis window opened from it.

---

## Step 9 — "It says hello but nothing happens"

**What happened (my report):** the desktop version spoke "Hello Mehr, Jarvis online", but did nothing when I spoke or typed.

**Cause (two likely ones; the AI could not see my screen, so both were fixed):**

1. In the window version, hands-free listening started **off** and nothing said so. The earlier terminal version asked "Voice mode?" and the window did not.
2. The speech-detection limit was a **fixed** sensitivity that can ignore a quiet laptop microphone completely.

**Fix:**

- hands-free **on by default** (and the choice is remembered);
- an **adaptive threshold** that measures the room's background level first, plus handling for speaking the instant listening starts;
- a start-up report in the chat (voice ready? which microphone? AI connected?), the real reason when voice libraries fail to load, and `mic test` / `status` commands;
- Jarvis waits a moment after speaking so it does not hear its own voice.

**Result:** I confirmed it was working properly on my laptop.

---

## Step 10 — Quality checks and documentation

- **146 automated checks** in three files (see the README's Testing section) using a simulated microphone, a fake text-to-speech engine and a fake Gemini server.
- **`pyflakes`** static check: no undefined names or unused code problems.
- **A review of what the tests cannot prove** — written down in the README's "Known limitations": real Gemini behaviour, real YouTube and LinkedIn pages, and Windows-specific features are checked by hand, not by the automated tests.
- This log, the README, `docs/CODE_TOUR.md`, `.gitignore` so personal files never get uploaded, and example files for the key and profile.

---

## Summary of bugs found and fixed

| # | Problem | Fix |
|---|---|---|
| 1 | PyAudio would not install | `sounddevice` + `numpy` |
| 2 | Gemini client closed immediately | Keep client in a module-level variable |
| 3 | Hard-coded model retired (404) | Discover models at start-up + fallback list |
| 4 | Servers overloaded (503) | Skip to next model; remember the one that worked |
| 5 | Frozen on "Thinking…" | Request timeouts |
| 6 | "I can't" for YouTube and LinkedIn requests | Local command parser before the AI; first-result lookup; job-search URL builder |
| 7 | Window opened but did not react | Hands-free default on; adaptive microphone threshold; diagnostics |
| 8 | `open <name>` tried to launch a program before looking for a file with that name (found while testing) | Order changed: websites → known apps → your files → other apps, with a blocklist |
