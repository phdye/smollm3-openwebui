"""Python virtual environment backend installer for Tomex.

This backend installs Open WebUI into a local Python virtual environment and
runs Ollama natively on Windows. It mirrors the behaviour previously embedded
in the Windows installer.
"""

from __future__ import annotations

import argparse

from . import windows


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack using a Python virtual environment."""
    parser = argparse.ArgumentParser(description="Install Tomex using pip/venv")
    parser.parse_args(argv)

    # 1) Ollama and model on the host
    windows.ensure_ollama_installed()
    windows.ensure_ollama_running_and_autostart()
    windows.ensure_smollm3_model()

    # 2) Open WebUI via pip and ffmpeg on the host
    windows.ensure_ffmpeg_on_host()
    windows.ensure_openwebui_pip()

    # 3) Helper scripts and shortcuts
    windows.create_start_stop_scripts("pip", None)
    windows.ensure_start_menu_shortcuts(None)
