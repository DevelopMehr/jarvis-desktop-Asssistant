"""Shared set-up for the tests.

Every test imports a *temporary copy* of jarvis.py. Jarvis stores its files (memory.json,
notes.txt, settings.json, outputs/) next to jarvis.py, so using a copy means the tests can
never touch your real notes, memory or settings.

Hardware and online services are replaced with fakes (text-to-speech, microphone, Google
Gemini server), so the tests run on any computer without audio devices or an API key.
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def prepare():
    """Copies jarvis.py into a temporary folder and puts that folder first on sys.path."""
    work = Path(tempfile.mkdtemp(prefix="jarvis_test_"))
    shutil.copy(ROOT / "jarvis.py", work / "jarvis.py")
    sys.path.insert(0, str(work))
    return work
