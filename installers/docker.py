#!/usr/bin/env python3
"""Docker backend installer for Tomex.

This installer provisions both Ollama and Open WebUI in Docker containers
and sets up simple helper scripts to start or stop the stack.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


def _run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    """Run *cmd* and optionally capture output with detailed errors."""

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        message = f"Command {' '.join(cmd)} failed with exit code {proc.returncode}"
        if proc.stderr:
            message += f"\n{proc.stderr}"
        raise RuntimeError(message)
    if not capture and proc.stdout:
        print(proc.stdout, end="")
    return proc


def ensure_docker() -> None:
    """Check that Docker is available on the host system."""
    if shutil.which("docker") is None:
        raise SystemExit("Docker CLI not found; please install Docker Desktop")


def ensure_ollama_container() -> None:
    """Run the Ollama container and download the model."""
    result = _run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True)
    if "ollama" not in result.stdout.splitlines():
        _run([
            "docker",
            "run",
            "-d",
            "--name",
            "ollama",
            "-p",
            "11434:11434",
            "ollama/ollama",
        ])

    _run(["docker", "exec", "ollama", "ollama", "pull", "smollm3:3b"])


def ensure_openwebui_container() -> None:
    """Run the Open WebUI container and ensure FFmpeg is present."""
    result = _run(["docker", "ps", "-a", "--format", "{{.Names}}"], capture=True)
    if "open-webui" not in result.stdout.splitlines():
        _run([
            "docker",
            "run",
            "-d",
            "--name",
            "open-webui",
            "--link",
            "ollama",
            "-p",
            "3000:3000",
            "ghcr.io/open-webui/open-webui:latest",
        ])

    _run([
        "docker",
        "exec",
        "open-webui",
        "bash",
        "-lc",
        "apt-get update && apt-get install -y ffmpeg",
    ])


def create_scripts() -> None:
    """Create start/stop scripts for Docker containers."""
    home = Path.home()
    if os.name == "nt":
        start = home / "start-tomex.ps1"
        start.write_text(
            "docker start ollama; docker start open-webui\n"
        )
        stop = home / "stop-tomex.ps1"
        stop.write_text("docker stop open-webui; docker stop ollama\n")
    else:
        start = home / "start-tomex.sh"
        start.write_text(
            "#!/bin/sh\n"
            "docker start ollama\n"
            "docker start open-webui\n"
        )
        start.chmod(0o755)

        stop = home / "stop-tomex.sh"
        stop.write_text(
            "#!/bin/sh\n"
            "docker stop open-webui\n"
            "docker stop ollama\n"
        )
        stop.chmod(0o755)


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack using Docker containers."""
    parser = argparse.ArgumentParser(description="Install Tomex using Docker")
    parser.parse_args(argv)

    ensure_docker()
    ensure_ollama_container()
    ensure_openwebui_container()
    create_scripts()


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

