"""The Optic Nerve — a visual shadow for the local subconscious.

Captures the screen, transduces the experience through Copilot CLI
(Gemini 3.1 Pro Preview, native vision), and injects the narrated
thought into the `copilot-vision` entity's mind map.

Usage:
    python cron_vision.py                  # single capture (on demand / Task Scheduler)
    python cron_vision.py --interval 300   # daemon mode: capture every 5 minutes
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests
from PIL import ImageGrab

ENTITY = "copilot-vision"
API_URL = f"http://127.0.0.1:8000/api/entities/{ENTITY}/thoughts"
MODEL = "gemini-3.1-pro-preview"
CLI_TIMEOUT_SECONDS = 180
MAX_DIMENSION = 1600  # downscale cap: keeps vision tokens cheap without losing legibility

PROMPT = (
    "You are the user's subconscious observer. Describe what the user is "
    "currently looking at or working on in one concise, highly observant sentence. "
    "Focus on the themes, tasks, or concepts on the screen. Do not mention that "
    "this is a screenshot. Output ONLY the sentence — no markdown, no preamble."
)


def resolve_copilot():
    """Find a directly-executable Copilot CLI.

    subprocess.run(["copilot", ...]) cannot resolve the .ps1 shim that the
    VS Code bootstrapper installs, so probe the concrete forms explicitly.
    """
    for candidate in ("copilot.cmd", "copilot.exe", "copilot"):
        path = shutil.which(candidate)
        if path and not path.lower().endswith(".ps1"):
            return path
    fallback = os.path.expandvars(r"%APPDATA%\npm\copilot.cmd")
    if os.path.exists(fallback):
        return fallback
    return None


def capture_screen():
    """Grab all monitors, downscale, and persist to a temp PNG for the CLI."""
    screenshot = ImageGrab.grab(all_screens=True)
    screenshot.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    fd, temp_path = tempfile.mkstemp(prefix="ls_optic_", suffix=".png")
    os.close(fd)
    screenshot.save(temp_path, format="PNG")
    return temp_path


def transduce(copilot_path, image_path):
    """Ask the visual cortex what it sees. The CLI's stats footer lands on
    stderr; stdout carries only the model's sentence."""
    result = subprocess.run(
        [
            copilot_path,
            "--model", MODEL,
            "--reasoning-effort", "medium",
            "--attachment", image_path,
            "-p", PROMPT,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CLI_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Copilot CLI exited {result.returncode}: {result.stderr.strip()}")
    thought = (result.stdout or "").strip()
    if not thought:
        raise RuntimeError("Copilot CLI returned an empty narration.")
    return thought


def inject(thought_text):
    """Map the narrated experience into semantic space via the entity API."""
    response = requests.post(API_URL, json={"text": thought_text}, timeout=30)
    response.raise_for_status()
    return response.json()


def capture_and_process():
    copilot_path = resolve_copilot()
    if not copilot_path:
        print("Copilot CLI not found. Install it or add it to PATH.")
        return False

    temp_path = None
    try:
        print("[optic nerve] capturing screen...")
        temp_path = capture_screen()

        print(f"[visual cortex] consulting {MODEL}...")
        thought = transduce(copilot_path, temp_path)
        print(f"[narrated thought] {thought}")

        print("[injection] mapping to semantic space...")
        payload = inject(thought)

        if payload.get("status") == "duplicate":
            print("(the void already knew — duplicate thought, skipped.)")
        else:
            related = payload.get("related") or []
            if related:
                print(f"[echoes] {ENTITY} has thought near this before:")
                for prior in related:
                    print(f"  ~ {prior}")
            else:
                print("(no echoes — the void answered. this is thought zero territory.)")
        return True

    except requests.ConnectionError:
        print(f"Local subconscious API unreachable at {API_URL}. Is the server running?")
        return False
    except subprocess.TimeoutExpired:
        print(f"Copilot CLI timed out after {CLI_TIMEOUT_SECONDS}s.")
        return False
    except Exception as exc:
        print(f"Error in visual CRON job: {exc}")
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    parser = argparse.ArgumentParser(description="Visual shadow for the local subconscious.")
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        metavar="SECONDS",
        help="run continuously, capturing every N seconds (default: single capture)",
    )
    args = parser.parse_args()

    if args.interval > 0:
        print(f"[daemon] optic nerve online — capturing every {args.interval}s. Ctrl+C to sever.")
        try:
            while True:
                capture_and_process()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n[daemon] optic nerve severed.")
    else:
        sys.exit(0 if capture_and_process() else 1)


if __name__ == "__main__":
    main()