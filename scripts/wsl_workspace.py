#!/usr/bin/env python3
"""Utilities for managing a persistent WSL workspace for smollm3-openwebui.

This script helps keep a WSL distribution active in the repository directory
and exposes commands to suspend or resume the environment.  It also ensures a
minimal toolchain (Python and Git) is available for basic editing and script
execution.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

DEFAULT_DISTRO = "Ubuntu"


def _to_wsl_path(path: str) -> str:
    """Convert a Windows path to its WSL equivalent.

    Paths already in POSIX form are returned unchanged.
    """

    p = Path(path)
    if p.drive:
        drive = p.drive.rstrip(":").lower()
        rest = "/".join(p.parts[1:])
        return f"/mnt/{drive}/{rest}"
    return str(p)


def _ensure_minimal_env(distro: str) -> None:
    """Install baseline tools inside the WSL distro if missing."""

    setup_cmd = (
        "command -v python3 >/dev/null 2>&1 || "
        "(sudo apt-get update && sudo apt-get install -y python3 python3-pip git)"
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", setup_cmd], check=True)


def start_workspace(distro: str, repo: str) -> None:
    """Open a shell in the WSL distro rooted at the repo path."""

    wsl_repo = _to_wsl_path(repo)
    _ensure_minimal_env(distro)
    cmd = [
        "wsl",
        "-d",
        distro,
        "bash",
        "-lc",
        f"cd '{wsl_repo}' && exec bash",
    ]
    subprocess.run(cmd, check=True)


def suspend_workspace(distro: str) -> None:
    """Suspend the given WSL distro."""

    subprocess.run(["wsl", "--terminate", distro], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage a persistent WSL workspace for smollm3-openwebui",
    )
    parser.add_argument(
        "action",
        choices=["start", "resume", "suspend"],
        help="Action to perform",
    )
    parser.add_argument(
        "--distro",
        default=DEFAULT_DISTRO,
        help="WSL distribution name (default: %(default)s)",
    )
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Path to the repository on the Windows side",
    )

    args = parser.parse_args()

    if args.action in {"start", "resume"}:
        start_workspace(args.distro, args.repo)
    else:
        suspend_workspace(args.distro)


if __name__ == "__main__":
    main()
