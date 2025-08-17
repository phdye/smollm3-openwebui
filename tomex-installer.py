#!/usr/bin/env python3
"""Wrapper around backend-specific installers.

This lightweight front-end chooses the appropriate installer backend and
forwards command-line arguments to it. Each backend lives in the
``installers`` package and exposes an ``install(argv)`` function.
"""

from __future__ import annotations

import argparse
import platform
from typing import Dict, Callable, List

from installers import windows, wsl, docker, pip_installer

BACKENDS: Dict[str, Callable[[List[str]], None]] = {
    "windows": windows.install,
    "wsl": wsl.install,
    "docker": docker.install,
    "pip": pip_installer.install,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Tomex installer wrapper")
    parser.add_argument(
        "--backend",
        choices=sorted(BACKENDS.keys()),
        help="Which backend installer to run",
    )
    args, remaining = parser.parse_known_args(argv)

    backend = args.backend
    if backend is None:
        if platform.system().lower() == "windows":
            backend = "windows"
        else:
            parser.error("--backend is required on non-Windows systems")

    BACKENDS[backend](remaining)


if __name__ == "__main__":
    main()
