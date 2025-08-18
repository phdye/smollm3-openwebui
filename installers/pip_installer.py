#!/usr/bin/env python3
"""Python virtual environment backend installer for Tomex.

This installer sets up Ollama and FFmpeg on the host system, creates a
dedicated virtual environment and installs Open WebUI within it. Simple
start/stop scripts are generated in the user's home directory.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise a detailed error on failure."""

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with exit code {proc.returncode}"
        )


def ensure_ollama() -> None:
    if shutil.which("ollama") is None:
        _run([
            "winget",
            "install",
            "--id",
            "Ollama.Ollama",
            "-e",
            "--silent",
        ])


def ensure_model() -> None:
    _run(["ollama", "pull", "smollm3:3b"])


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        _run([
            "winget",
            "install",
            "--id",
            "Gyan.FFmpeg",
            "-e",
            "--silent",
        ])


def ensure_openwebui(venv: Path) -> None:
    if not venv.exists():
        _run([sys.executable, "-m", "venv", str(venv)])

    pip_path = venv / ("Scripts" if os.name == "nt" else "bin") / "pip"
    _run([str(pip_path), "install", "--upgrade", "open-webui"])


def create_scripts(venv: Path) -> None:
    home = Path.home()
    if os.name == "nt":
        start = home / "start-tomex.ps1"
        start.write_text(
            f"& '{venv / 'Scripts' / 'open-webui.exe'}' --host 0.0.0.0\n"
        )
        stop = home / "stop-tomex.ps1"
        stop.write_text(
            "Stop-Process -Name 'open-webui' -ErrorAction SilentlyContinue\n"
        )
    else:
        start = home / "start-tomex.sh"
        start.write_text(
            f"#!/bin/sh\n{venv / 'bin' / 'open-webui'} --host 0.0.0.0 &\n"
        )
        start.chmod(0o755)

        stop = home / "stop-tomex.sh"
        stop.write_text("#!/bin/sh\npkill -f 'open-webui'\n")
        stop.chmod(0o755)


def install(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Install Tomex using pip/venv")
    parser.parse_args(argv)

    venv = Path.home() / "tomex-venv"

    ensure_ollama()
    ensure_model()
    ensure_ffmpeg()
    ensure_openwebui(venv)
    create_scripts(venv)


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
