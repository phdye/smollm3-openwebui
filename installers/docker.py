"""Docker backend installer for Tomex.

This backend runs Open WebUI in a Docker container while Ollama runs on the
Windows host. Helper routines from the Windows installer perform the actual
setup steps.
"""

from __future__ import annotations

import argparse

from . import windows


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack using Docker for Open WebUI.

    Parameters
    ----------
    argv:
        Optional list of CLI arguments from the wrapper.
    """
    parser = argparse.ArgumentParser(description="Install Tomex using Docker")
    parser.parse_args(argv)

    # 1) Ensure Ollama and model on the host
    windows.ensure_ollama_installed()
    windows.ensure_ollama_running_and_autostart()
    windows.ensure_smollm3_model()

    # 2) Run Open WebUI in Docker and ensure ffmpeg is available inside
    windows.ensure_openwebui_docker()
    windows.ensure_ffmpeg_in_container("open-webui")

    # 3) Create helper scripts and Start Menu entries
    windows.create_start_stop_scripts("docker", None)
    windows.ensure_start_menu_shortcuts(None)
