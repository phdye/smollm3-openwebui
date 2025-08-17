"""WSL backend installer for Tomex.

This backend installs the Tomex stack while running Open WebUI inside a
specified WSL distribution. It reuses helper functions from the Windows
installer to perform the heavy lifting.
"""

from __future__ import annotations

import argparse

from . import windows


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack using a WSL distribution.

    Parameters
    ----------
    argv:
        Optional list of CLI arguments forwarded from the wrapper.
    """
    parser = argparse.ArgumentParser(description="Install Tomex using WSL")
    parser.add_argument(
        "--distro",
        required=True,
        help="Name of the WSL distribution to install Open WebUI into",
    )
    args = parser.parse_args(argv)

    # 1) Ensure Ollama and model on the Windows host
    windows.ensure_ollama_installed()
    windows.ensure_ollama_running_and_autostart()
    windows.ensure_smollm3_model()

    # 2) Install Open WebUI inside the target WSL distribution
    windows.ensure_openwebui_wsl(args.distro)

    # 3) Create convenience scripts and shortcuts
    windows.create_start_stop_scripts("wsl", args.distro)
    windows.ensure_start_menu_shortcuts(args.distro)
