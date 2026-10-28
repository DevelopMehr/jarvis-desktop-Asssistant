# install_jarvis.py - one-time setup for Jarvis (Windows)
#
# Run it by double-clicking "Install Jarvis.bat". It will:
#   1. install the Python libraries Jarvis needs
#   2. put a "Jarvis" shortcut on your Desktop and in the Start menu
#      (opens the Jarvis window directly, no black console, no VS Code)
#   3. optionally make Jarvis start when Windows starts
#
# Run with --dry-run to see what it WOULD do without changing anything.

import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = ["pyttsx3", "SpeechRecognition", "sounddevice", "numpy", "google-genai"]
DRY = "--dry-run" in sys.argv


def ps_quote(text):
    return str(text).replace("'", "''")


def powershell(script):
    if DRY:
        print("  [dry-run] PowerShell:", script)
        return ""
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                            capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "PowerShell failed")
    return result.stdout.strip()


def special_folder(name):
    if DRY:
        return Path("C:/Users/You") / name
    return Path(powershell(f"[Environment]::GetFolderPath('{name}')"))


def install_packages():
    failed = []
    for pkg in PACKAGES:
        print(f"  Installing {pkg} ...")
        if DRY:
            continue
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", pkg])
        if r.returncode != 0:
            failed.append(pkg)
    return failed


def make_shortcut(link, target, arguments, workdir, icon):
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{ps_quote(link)}'); "
        f"$s.TargetPath = '{ps_quote(target)}'; "
        f"$s.Arguments = '{ps_quote(arguments)}'; "
        f"$s.WorkingDirectory = '{ps_quote(workdir)}'; "
        f"$s.IconLocation = '{ps_quote(icon)}'; "
        "$s.Description = 'Jarvis personal assistant'; $s.Save()")
    powershell(script)


def ask(question):
    try:
        return input(question).strip().lower().startswith("y")
    except EOFError:
        return False


def main():
    print("=" * 50)
    print("  Jarvis installer")
    print("=" * 50)
    if platform.system() != "Windows" and not DRY:
        print("This installer is for Windows.")
        return
    if sys.version_info < (3, 9):
        print("Python 3.9 or newer is needed. Install it from python.org.")
        return
    if not DRY:
        try:
            import tkinter  # noqa: F401
        except ImportError:
            print("Your Python has no 'tkinter' (needed for the window).")
            print("Reinstall Python from python.org and keep 'tcl/tk and IDLE' ticked.")
            return

    jarvis = HERE / "jarvis.py"
    if not jarvis.exists():
        print("jarvis.py was not found next to this installer.")
        return

    print("\n1. Installing libraries (this can take a few minutes)...")
    failed = install_packages()
    if failed:
        print("\n  These could not be installed:", ", ".join(failed))
        print("  Jarvis will still open. Voice or the AI brain may not work until they install.")

    pythonw = Path(sys.executable).with_name("pythonw.exe")
    target = pythonw if pythonw.exists() or DRY else Path(sys.executable)
    icon = HERE / "jarvis.ico"
    args = f'"{jarvis}"'

    print("\n2. Creating shortcuts...")
    desktop = special_folder("Desktop")
    programs = special_folder("Programs")
    for folder in (desktop, programs):
        link = folder / "Jarvis.lnk"
        make_shortcut(link, target, args, HERE, icon)
        print("  Created:", link)

    print("\n3. Start with Windows (optional)")
    if ask("   Start Jarvis automatically when Windows starts? (y/n): "):
        link = special_folder("Startup") / "Jarvis.lnk"
        make_shortcut(link, target, args, HERE, icon)
        print("  Created:", link)

    print("\nChecking your files...")
    for name, hint in (("api_key.txt", "needed for the AI brain"),
                       ("profile.txt", "needed for job answers")):
        print(f"  {'OK     ' if (HERE / name).exists() else 'MISSING'} {name} ({hint})")

    print("\nDone. Double-click the Jarvis icon on your Desktop to start it.")
    print("Tip: right-click the Desktop icon > Show more options > Pin to taskbar.")
    if not DRY and ask("\nOpen Jarvis now? (y/n): "):
        subprocess.Popen([str(target), str(jarvis)], cwd=str(HERE))


if __name__ == "__main__":
    main()
