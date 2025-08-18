#!/usr/bin/env python3
"""Wrapper around backend-specific installers.

This lightweight front-end chooses the appropriate installer backend and
forwards command-line arguments to it. Each backend lives in the
``installers`` package and exposes an ``install(argv)`` function.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys


BACKENDS: dict[str, str] = {
    "windows": "installers.windows",
    "wsl": "installers.wsl",
    "docker": "installers.docker",
    "pip": "installers.pip_installer",
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

    module = BACKENDS[backend]

    if backend == "wsl" and platform.system().lower() == "windows":
        cmd = ["wsl"]
        if args.distro:
            cmd += ["-d", args.distro]
        cmd += ["python3", "-m", module, *remaining]
    else:
        cmd = [sys.executable, "-m", module, *remaining]

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
