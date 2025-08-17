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
from pathlib import Path


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise if it fails.

    Each command is printed before execution so users can see what the
    installer is doing, providing the blow-by-blow output requested.
    """

    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


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
    _run(["ollama", "pull", "smollm3:3b"])


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
