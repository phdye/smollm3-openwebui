#!/usr/bin/env python3
"""TomEx installer script.

This script bootstraps a minimal Open WebUI + Ollama stack.  It previously
spawned the Ollama server using the Windows binary even when a WSL
installation was requested.  This version writes a ``start-tomex.cmd`` that
runs **both** Ollama and Open WebUI inside the chosen WSL distribution.
"""

import argparse
import os
from pathlib import Path


START_SCRIPT_NAME = "start-tomex.cmd"


def write_start_script(base: Path, distro: str) -> Path:
    """Create the start script that launches Ollama and Open WebUI in WSL."""
    script_path = base / START_SCRIPT_NAME
    base.mkdir(parents=True, exist_ok=True)

    with open(script_path, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        # Start Ollama inside WSL in a detached console.
        f.write(
            f'start "" wsl -d {distro} sh -lc "ollama serve"\n'
        )
        # Launch Open WebUI in the same WSL distro once Ollama is running.
        f.write(
            f'wsl -d {distro} sh -lc "env OLLAMA_BASE_URL=\\"http://localhost:11434\\" '
            '~/.open-webui-venv/bin/open-webui serve --host 0.0.0.0 --port 3000"\n'
        )

    return script_path


def main() -> None:
    parser = argparse.ArgumentParser(description="TomEx installer")
    parser.add_argument(
        "--wsl",
        dest="wsl_distro",
        help="Name of the WSL distribution to use",
    )
    args = parser.parse_args()

    if not args.wsl_distro:
        raise SystemExit("--wsl <distro> is required")

    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "tomex"
    script_path = write_start_script(base, args.wsl_distro)
    print(f"Wrote start script to {script_path}")


if __name__ == "__main__":
    main()
