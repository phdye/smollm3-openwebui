#!/usr/bin/env python3
"""Utilities for managing a persistent WSL workspace for smollm3-openwebui.

This script helps keep a WSL distribution active in the repository directory
and exposes commands to suspend or resume the environment.  Phase 2 expands the
toolchain setup so that common development languages and tooling are
preinstalled, enabling immediate linting, building and testing.
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


def _ensure_dev_env(distro: str) -> None:
    """Install developer tooling inside the WSL distro if missing."""

    packages = [
        "build-essential",
        "clang",
        "git",
        "python3",
        "python3-pip",
        "python3-venv",
        "cargo",
        "rustc",
        "flake8",
        "pytest",
    ]
    pkg_str = " ".join(packages)
    setup_cmd = (
        "sudo apt-get update && "
        f"sudo apt-get install -y {pkg_str}"
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", setup_cmd], check=True)


def _run_in_wsl(distro: str, repo: str, cmd: str) -> None:
    """Execute a command inside the WSL distro rooted at the repo path."""

    wsl_repo = _to_wsl_path(repo)
    subprocess.run(
        ["wsl", "-d", distro, "bash", "-lc", f"cd '{wsl_repo}' && {cmd}"],
        check=True,
    )


def start_workspace(distro: str, repo: str) -> None:
    """Open a shell in the WSL distro rooted at the repo path."""

    _ensure_dev_env(distro)
    _run_in_wsl(distro, repo, "exec bash")


def suspend_workspace(distro: str) -> None:
    """Suspend the given WSL distro."""

    subprocess.run(["wsl", "--terminate", distro], check=True)


def run_tests(distro: str, repo: str) -> None:
    """Run pytest inside the WSL distro."""

    _ensure_dev_env(distro)
    _run_in_wsl(distro, repo, "pytest")


def run_lint(distro: str, repo: str) -> None:
    """Run flake8 over the repository inside the WSL distro."""

    _ensure_dev_env(distro)
    _run_in_wsl(distro, repo, "flake8 .")


def run_build(distro: str, repo: str) -> None:
    """Attempt to build the project using common conventions."""

    _ensure_dev_env(distro)
    build_cmd = (
        "if [ -f Cargo.toml ]; then cargo build; "
        "elif [ -f Makefile ]; then make; "
        "elif [ -f setup.py ]; then python3 setup.py build; "
        "else echo 'No build step defined.'; fi"
    )
    _run_in_wsl(distro, repo, build_cmd)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage a persistent WSL workspace for smollm3-openwebui",
    )
    parser.add_argument(
        "action",
        choices=["start", "resume", "suspend", "test", "lint", "build"],
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
    elif args.action == "suspend":
        suspend_workspace(args.distro)
    elif args.action == "test":
        run_tests(args.distro, args.repo)
    elif args.action == "lint":
        run_lint(args.distro, args.repo)
    elif args.action == "build":
        run_build(args.distro, args.repo)


if __name__ == "__main__":
    main()
