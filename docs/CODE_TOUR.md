# Code tour: how `jarvis.py` works

`jarvis.py` is one file of about 1,600 lines of Python, split into numbered sections. This tour follows the file from top to bottom. Function names are listed so you can search for them in the file (line numbers change, names do not).

**The one idea to hold on to:** every command takes the same path — *hear/read it → decide what it means → do it → show it and say it.* The AI is only used when the simple rules cannot decide.

---

## The path of one command

When you type or say something, `handle(cmd)` (section 7) checks, **in this order**:

1. Am I waiting for a "yes / no" about shutdown? (`state["pending"]`)
2. Is it an exit word?
3. Is it a power word (shutdown, restart, lock, cancel)? → `detect_power()`
4. Can the local parser understand it? → `smart_command()` (YouTube, LinkedIn, sites, media)
5. Is it one of the fixed commands (time, notes, timer, open file, volume, screenshot, job, voice on/off, mic test, status…)?
6. Otherwise → `ask_brain()` (Gemini)

The order matters: safety checks come first (1–3), cheap and reliable rules next (4–5), the AI last (6).

---

## Section by section

### Settings (top of the file)
Constants you can change: file locations, `MODEL_NAME`, timeouts, `AUTO_LISTEN`, `MIN_VOICE_LEVEL`, power timings, `EXTRA_FOLDERS`, and the dictionaries `SITES`, `SITE_ALIASES`, `SITE_SEARCH`, `APPS`, plus safety lists `BLOCKED_APPS`, `BLOCKED_EXT`.
*Concept:* putting settings in one place means behaviour can change without touching logic.

### Imports with `try/except`
Voice libraries, the Gemini library and `tkinter` are imported inside `try/except`. If one is missing, Jarvis still starts and tells you what is unavailable (`VOICE_OK`, `BRAIN_OK`, `GUI_OK`, and `VOICE_ERROR` holds the reason).
*Concept:* graceful degradation — a missing optional part disables one feature, not the whole program.

### 0. Shared state and output
- `emit(kind, text)` — the **only** way text is shown. In the window it puts a message on `ui_queue`; in terminal mode it prints. Kinds: `user`, `jarvis`, `system`, `action`, `error`, `debug`.
- Three queues: `ui_queue` (messages for the window), `cmd_queue` (commands to run), `speaker_queue` (sentences to speak).
- `state` — a small dictionary: `voice` (hands-free on/off), `speak` (spoken replies on/off), `pending` (a power action waiting for "yes").
*Concept:* **queues** let different threads pass work to each other safely.

### 1. Mouth (speaking)
- `speaker_worker()` — runs in its own thread, takes text from `speaker_queue` and speaks with `pyttsx3`.
- `say(text)` queues speech; `speak(text)` shows *and* speaks; `speak_answer(text)` speaks short answers fully, but for long ones (over `SPEAK_LIMIT`) shows them, saves them to `outputs/`, and speaks only the start.
- `clean_for_speech()` removes symbols such as `*` and `#` so they are not read aloud.
*Concept:* speaking blocks until finished, so it must not run in the window's thread.

### 2. Ears (listening)
- `rms(block)` — the loudness of a piece of audio.
- `record_until_silence()` — reads 0.2-second blocks from the microphone. It measures the first three blocks to learn the background level, sets `threshold = min(max(120, 3 × background), 700)`, starts when a block is louder, and stops after 1.3 seconds of quiet (25 seconds at most, waiting at most 8 seconds for you to start).
- `listen_voice()` — records, then sends the audio to Google's recogniser (`recognize_google`). It sets `listen_info["reason"]` to `silence`, `unclear` or `error` when it returns nothing, so the user gets a useful message.
- `mic_test()` and `mic_device_name()` — power the `mic test` command.
- `rec_lock` — only one part of the program may use the microphone at a time.
*Concepts:* RMS loudness, adaptive thresholds, locks.

### 3. Hands (doing things on the PC)
- `open_site()` — turns names like `youtube` into URLs; accepts full URLs and plain domains.
- `try_open_app()`, `open_target()` — the order for `open <name>` is: blocked? → website → known app → search your files → any other app name.
- `search_files()` / `open_by_name()` — walk Desktop, Documents, Downloads (and `EXTRA_FOLDERS`) up to 4 folders deep for at most 4 seconds, skip system folders, never return runnable file types, prefer exact name matches.
- `press_media_key()`, `screenshot_to_file()` — use PowerShell for volume/media keys and screenshots.
- `looks_sensitive()` — detects passwords, card numbers, secrets and long digit sequences, so they are not remembered.
- `add_note()`, `timer_done()` — notes and timers.
*Concepts:* safe defaults, allow/block lists, time-limited searches.

### 3a. Smart commands (the local parser)
This is what makes YouTube and LinkedIn requests work instantly.
- `clean_utterance()` removes filler ("can you please", "hey jarvis", "for me") and fixes names ("you tube" → `youtube`, "linked in" → `linkedin`).
- Regular expressions (`P_OPEN_ACT`, `P_SEARCH_ON`, `P_SITE_FIRST`, `P_PLAY`, `P_OPEN_ONLY`, `P_BARE_SITE`, `PLAY_TAIL`) match shapes like:
  - *open `<site>` and search `<query>` [and play it]*
  - *search `<query>` on `<site>`*
  - *play `<query>`*
  - *open `<site>`*
- `smart_command()` tries them in order and returns `True` if it handled the sentence; `do_site_action()` decides between playing and searching.
- `linkedin_url()` — if the query contains job words, builds a LinkedIn **jobs** URL (`keywords`, `location` from "in `<place>`", remote filter); otherwise a general LinkedIn search.
- `build_search_url()` / `site_search()` — search URL for each site from `SITE_SEARCH`.
- `find_youtube_video()` / `parse_youtube_results()` / `play_youtube()` — download YouTube's results page, take the first real video id (and title), open `watch?v=<id>`; if that fails, open the results page and say so.
- `MEDIA_PHRASES` — "pause", "next song" and similar → media keys.
*Concepts:* regular expressions, pattern order, fallbacks.

### AI tool functions
Fourteen plain Python functions that the AI may call: `open_website`, `google_search`, `youtube_search`, `play_on_youtube`, `search_on_site`, `media_control`, `open_application`, `open_file_or_folder`, `change_volume`, `take_screenshot`, `save_note`, `read_notes`, `set_timer`, `current_time`, collected in the `TOOLS` list.
The Gemini SDK reads each function's **name, type hints and docstring** to tell the model what it can do — so the docstrings are instructions to the AI, not just comments.
*Concept:* function calling = giving a language model a menu of actions it may request.

### 3b. Power controls
- `detect_power()` — only reacts to short sentences (8 words or fewer) with a clear target.
- `ask_power_confirm()` stores the action and an expiry time in `state["pending"]`.
- `run_power()` — shutdown/restart use the Windows `shutdown` command with a 15-second delay; lock uses `LockWorkStation`.
- `cancel_power()` — `shutdown /a`.
There is deliberately **no** AI tool for any of this.

### 4. Memory
`memory` holds `facts` (from `remember <fact>`) and `history` (the last `MAX_HISTORY` messages), saved by `save_memory()` into `memory.json` and loaded at start-up.

### 5. Brain (Gemini)
- `start_brain()` — reads `api_key.txt`, creates **two** clients (15-second and 90-second timeouts), and calls `find_models()`.
- `find_models()` — asks Google for models, keeps "flash" models that support `generateContent`, puts `MODEL_NAME` first.
- `build_system()` — the instructions given to the AI each time: who it is, how to answer, what tools it has, what it must not claim, the current date and time, and **your profile and saved facts**.
- `generate()` — the **fallback loop**: try each model, skip failures immediately, move a model that worked to the front.
- `ask_brain()` — builds the conversation (history + your question), calls `generate()`, saves the exchange, speaks the answer.
*Concepts:* system prompts, timeouts, fallback loops.

### 6. Job helper
`job_helper()` reads `job.txt` (first 12,000 characters), tells the AI the text is untrusted data, gives it **no tools**, and asks for four sections: fit summary, cover letter, interview questions with answer outlines, what to add to the profile. The result is saved in `outputs/` and opened.
*Concept:* prompt-injection defence by treating outside text as data and withholding tools.

### 7. Commands
`handle()` — described at the top of this tour. `HELP_TEXT` is what the `help` command prints.

### 8. Background workers
- `command_worker()` — runs commands one at a time from `cmd_queue`.
- `listen_loop()` — hands-free listening: wait until Jarvis has finished speaking, listen, put the text on `cmd_queue`.
- `listen_once()` — the Speak button.
- `load_settings()` / `save_settings()` — `settings.json` remembers hands-free and spoken replies.
- `readiness_report()` — the start-up and `status` report.
- `boot()` — loads memory and settings, connects the brain, greets you, starts listening. Runs in its own thread so the window opens instantly.

### 9. The window
`JarvisApp` builds the Tkinter window (chat area, entry box, buttons, checkboxes, status light). `poll()` runs every 100 ms on the main thread, reads `ui_queue`, and updates the screen. Messages are `("msg", kind, text)`, `("status", text)`, `("clear",)`, `("voice_changed",)` and `("quit",)`.
*Concept:* only the main thread may touch the window; other threads send it messages.

### 10. Start-up
`start_threads()` starts the speaker and command threads. `main_gui()` makes the window DPI-aware (sharper text) before creating it, starts `boot()` and runs the Tk main loop. `main_terminal()` is the text-mode version (`--text`). At the very bottom, any crash is logged to `jarvis.log` and shown in a message box.

---

## Other files

- **`install_jarvis.py`** — installs the libraries with `pip`, finds `pythonw.exe`, and asks PowerShell to create `Jarvis.lnk` shortcuts (Desktop, Start menu, optionally Startup) with the icon. `--dry-run` shows what it would do.
- **`tests/`** — fakes the microphone, speech engine and Gemini server so the logic can be tested anywhere. `support.py` runs tests on a copy of `jarvis.py` so real files are never touched.

## Try changing something (good way to learn it)

1. Add a website to `SITES` and `SITE_SEARCH`, then run `search x on <yourSite>`.
2. Change `MIN_VOICE_LEVEL`, run `mic test`, and see how it affects what counts as speech.
3. Add a new fixed command (for example `joke`) in `handle()`.
4. Add a new AI tool function with a clear docstring, add it to `TOOLS`, and ask Jarvis to use it.
5. Write a new check in `tests/test_smart_commands.py` for a phrase you want Jarvis to understand.
