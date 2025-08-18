#!/usr/bin/env python3
"""WSL backend installer for Tomex.

This installer runs entirely inside a WSL distribution. It ensures that
Ollama, the SmolLM3 model, Open WebUI and FFmpeg are installed within the
distribution, creates simple start/stop helper scripts in the user's home
directory and starts the stack immediately.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise if it fails.

    Each command is printed before execution so users can see what the
    installer is doing, providing the blow-by-blow output requested.
    """

    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _wait_for_ollama(timeout: int = 60) -> None:
    """Block until the Ollama API is responsive."""

    url = "http://127.0.0.1:11434/api/version"
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except urllib.error.URLError:
            time.sleep(1)
    raise RuntimeError("Ollama server not responding")


def _ollama_running() -> bool:
    """Return ``True`` if the Ollama API is responding."""

    url = "http://127.0.0.1:11434/api/version"
    try:
        urllib.request.urlopen(url, timeout=1)
        return True
    except urllib.error.URLError:
        return False


def ensure_ollama() -> None:
    """Install Ollama if it is not already available."""
    print("Ensuring Ollama is installed...", flush=True)
    if shutil.which("ollama") is None:
        _run(["bash", "-lc", "curl -fsSL https://ollama.ai/install.sh | sh"])
    else:
        print("Ollama already present", flush=True)


def ensure_model() -> None:
    """Download the SmolLM3 model."""
    print("Fetching SmolLM3 model...", flush=True)
    server: subprocess.Popen[str] | None = None
    if not _ollama_running():
        server = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    _wait_for_ollama()
    _run(["ollama", "pull", "smollm3:3b"])
    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def ensure_ffmpeg() -> None:
    """Ensure FFmpeg is installed via apt."""
    print("Checking for FFmpeg...", flush=True)
    if shutil.which("ffmpeg") is None:
        _run(["sudo", "apt-get", "update"])
        _run(["sudo", "apt-get", "install", "-y", "ffmpeg"])
    else:
        print("FFmpeg already present", flush=True)


def ensure_openwebui() -> None:
    """Install Open WebUI using pip."""
    print("Installing/upgrading Open WebUI...", flush=True)
    _run([sys.executable, "-m", "pip", "install", "--upgrade", "open-webui"])


def create_scripts() -> None:
    """Create start/stop scripts in the user's home directory."""
    print("Creating helper scripts...", flush=True)
    home = Path.home()
    start = home / "start-tomex.sh"
    start.write_text(
        "#!/bin/bash\n"
        "ollama serve &\n"
        "open-webui --host 0.0.0.0 &\n"
    )
    start.chmod(0o755)

    stop = home / "stop-tomex.sh"
    stop.write_text(
        "#!/bin/bash\n"
        "pkill -f 'open-webui'\n"
        "pkill -f 'ollama serve'\n"
    )
    stop.chmod(0o755)


def start_stack() -> None:
    """Start the Tomex stack using the helper script."""
    print("Starting Tomex...", flush=True)
    start = Path.home() / "start-tomex.sh"
    _run([str(start)])


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack inside the current WSL distribution."""
    parser = argparse.ArgumentParser(description="Install Tomex inside WSL")
    parser.parse_args(argv)

    ensure_ollama()
    ensure_model()
    ensure_ffmpeg()
    ensure_openwebui()
    create_scripts()
    start_stack()


if __name__ == "__main__":
    install()
