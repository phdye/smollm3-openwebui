"""WSL backend installer for Tomex.

This installer runs entirely inside a WSL distribution. It ensures that
Ollama, the SmolLM3 model, Open WebUI and FFmpeg are installed within the
distribution and creates simple start/stop helper scripts in the user's
home directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise if it fails."""
    subprocess.run(cmd, check=True)


def ensure_ollama() -> None:
    """Install Ollama if it is not already available."""
    if shutil.which("ollama") is None:
        _run(["bash", "-lc", "curl -fsSL https://ollama.ai/install.sh | sh"])


def ensure_model() -> None:
    """Download the SmolLM3 model."""
    _run(["ollama", "pull", "smollm3:3b"])


def ensure_ffmpeg() -> None:
    """Ensure FFmpeg is installed via apt."""
    if shutil.which("ffmpeg") is None:
        _run(["sudo", "apt-get", "update"])
        _run(["sudo", "apt-get", "install", "-y", "ffmpeg"])


def ensure_openwebui() -> None:
    """Install Open WebUI using pip."""
    _run([sys.executable, "-m", "pip", "install", "--upgrade", "open-webui"])


def create_scripts() -> None:
    """Create start/stop scripts in the user's home directory."""
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


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack inside the current WSL distribution."""
    parser = argparse.ArgumentParser(description="Install Tomex inside WSL")
    parser.parse_args(argv)

    ensure_ollama()
    ensure_model()
    ensure_ffmpeg()
    ensure_openwebui()
    create_scripts()

