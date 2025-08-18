#!/usr/bin/env python3
"""Wrapper around backend-specific installers.

This lightweight front-end chooses the appropriate installer backend and
forwards command-line arguments to it. Each backend lives in the
``installers`` package and exposes an ``install(argv)`` function.
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
from pathlib import Path


BACKENDS: dict[str, str] = {
    "windows": "installers.windows",
    "wsl": "installers.wsl",
    "docker": "installers.docker",
    "pip": "installers.pip_installer",
}


def _create_start_menu_shortcuts_wsl(distro: str | None) -> None:
    """Create Start Menu shortcuts to manage a WSL-backed Tomex install."""

    appdata = os.environ.get("APPDATA")
    if not appdata:
        return

    base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "tomex"
    base.mkdir(parents=True, exist_ok=True)

    distro_opt = f"-d {distro} " if distro else ""

    start_script = base / "start-tomex.cmd"
    stop_script = base / "stop-tomex.cmd"
    start_script.write_text(
        "@echo off\n"
        f"wsl {distro_opt}-u root sh -lc \"~/start-tomex.sh\"\n",
        encoding="utf-8",
    )
    stop_script.write_text(
        "@echo off\n"
        f"wsl {distro_opt}-u root sh -lc \"~/stop-tomex.sh\"\n",
        encoding="utf-8",
    )

    sm_dir = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Tomex"
    sm_dir.mkdir(parents=True, exist_ok=True)
    for src, name in [(start_script, "Start Tomex.cmd"), (stop_script, "Stop Tomex.cmd")]:
        with open(sm_dir / name, "w", encoding="utf-8") as f:
            f.write(f"@echo off\n\"{src}\"\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tomex installer wrapper")
    parser.add_argument(
        "--backend",
        choices=sorted(BACKENDS.keys()),
        help="Which backend installer to run",
    )
    parser.add_argument(
        "--distro",
        help="WSL distribution name (default distribution is used if omitted)",
    )
    args, remaining = parser.parse_known_args(argv)

    backend = args.backend
    if backend is None:
        if platform.system().lower() == "windows":
            backend = "windows"
        else:
            parser.error("--backend is required on non-Windows systems")

    if args.distro and backend != "wsl":
        parser.error("--distro is only valid with --backend wsl")

    module = BACKENDS[backend]

    if backend == "wsl" and platform.system().lower() == "windows":
        cmd = ["wsl"]
        if args.distro:
            cmd += ["-d", args.distro]
        cmd += ["-u", "root", "python3", "-m", module, *remaining]
        subprocess.run(cmd, check=True)
        _create_start_menu_shortcuts_wsl(args.distro)
    else:
        cmd = [sys.executable, "-m", module, *remaining]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
