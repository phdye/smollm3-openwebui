#!/usr/bin/env python3
"""Wrapper around backend-specific installers.

This lightweight front-end chooses the appropriate installer backend and
forwards command-line arguments to it. Each backend lives in the
``installers`` package and exposes an ``install(argv)`` function.
"""

from __future__ import annotations

import argparse
import importlib
import platform
import subprocess
from typing import Dict, Callable, List

def _lazy(module: str) -> Callable[[List[str]], None]:
    """Return a callable that imports ``module`` on demand and runs its
    ``install`` function."""

    def _runner(args: List[str]) -> None:
        importlib.import_module(module).install(args)

    return _runner


BACKENDS: Dict[str, Callable[[List[str]], None]] = {
    "windows": _lazy("installers.windows"),
    "wsl": _lazy("installers.wsl"),
    "docker": _lazy("installers.docker"),
    "pip": _lazy("installers.pip_installer"),
}


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

    if backend == "wsl" and platform.system().lower() == "windows":
        cmd = ["wsl"]
        if args.distro:
            cmd += ["-d", args.distro]
        cmd += ["python3", "-m", "installers.wsl", *remaining]
        subprocess.run(cmd, check=True)
    else:
        BACKENDS[backend](remaining)


if __name__ == "__main__":
    main()
