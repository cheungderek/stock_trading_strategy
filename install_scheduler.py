#!/usr/bin/env python3
"""
install_scheduler.py - install / uninstall the macOS LaunchAgent that runs
the Donchian scanner every weekday at 21:30 local time (after US market close).

Usage:
  python3 install_scheduler.py install     # install and load the LaunchAgent
  python3 install_scheduler.py uninstall   # unload and remove the LaunchAgent
  python3 install_scheduler.py status      # show current install status
  python3 install_scheduler.py test        # trigger a one-off run now
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLIST_TEMPLATE = HERE / "com.derekc.donchian-scanner.plist"
LABEL = "com.derekc.donchian-scanner"
INSTALL_DIR = Path.home() / "Library" / "LaunchAgents"
INSTALLED_PLIST = INSTALL_DIR / f"{LABEL}.plist"


def _fill_template() -> str:
    text = PLIST_TEMPLATE.read_text()
    return text.replace("__PROJECT_DIR__", str(HERE))


def install():
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    plist_text = _fill_template()
    INSTALLED_PLIST.write_text(plist_text)
    print(f"Installed plist to: {INSTALLED_PLIST}")
    # Unload if already loaded, then load fresh
    subprocess.run(["launchctl", "unload", str(INSTALLED_PLIST)],
                   check=False, capture_output=True)
    res = subprocess.run(["launchctl", "load", str(INSTALLED_PLIST)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Failed to load: {res.stderr}")
        sys.exit(1)
    print(f"LaunchAgent '{LABEL}' loaded successfully.")
    print("Scanner will run every Mon-Fri at 17:30 local time (5:30 PM ET, ~30 min after US close).")
    # Show next run approx (just informational)
    print("\nTo verify, run:  python3 install_scheduler.py status")
    print("To test now, run:  python3 install_scheduler.py test")


def uninstall():
    if INSTALLED_PLIST.exists():
        subprocess.run(["launchctl", "unload", str(INSTALLED_PLIST)],
                       check=False, capture_output=True)
        INSTALLED_PLIST.unlink()
        print(f"Removed: {INSTALLED_PLIST}")
    else:
        print("Nothing to uninstall (plist not installed).")


def status():
    if not INSTALLED_PLIST.exists():
        print("Status: NOT INSTALLED")
        return
    res = subprocess.run(["launchctl", "list", LABEL],
                          capture_output=True, text=True)
    if res.returncode == 0:
        print("Status: LOADED")
        print(res.stdout)
    else:
        print("Status: INSTALLED but not loaded (use `install` to load)")


def test():
    """Trigger scanner now (foreground, so you see live output)."""
    script = HERE / "src" / "scan_daily.py"
    py = "/opt/homebrew/bin/python3"
    print(f"Running: {py} {script}")
    res = subprocess.run([py, str(script)])
    sys.exit(res.returncode)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "install":
        install()
    elif cmd == "uninstall":
        uninstall()
    elif cmd == "status":
        status()
    elif cmd == "test":
        test()
    else:
        print(__doc__)
        sys.exit(1)
