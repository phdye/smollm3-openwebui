"""WSL backend installer for Tomex.

This installer runs inside a WSL distribution but intentionally keeps
``ollama`` on the Windows host so it can talk to the GPU directly. Only
Open WebUI and FFmpeg are provisioned in WSL, and helper scripts are
created to launch the interface while using the host's Ollama service.
"""

from __future__ import annotations

import argparse
import pwd
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path


APP_USER = "tomex"


def _run(cmd: list[str]) -> None:
    """Run *cmd* and raise if it fails.

    Each command is printed before execution so users can see what the
    installer is doing, providing the blow-by-blow output requested.
    """

    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command {' '.join(cmd)} failed with exit code {proc.returncode}"
        )


def _windows_host_ip() -> str:
    """Return the IP address of the Windows host.

    WSL exposes the Windows host as the first nameserver in ``/etc/resolv.conf``.
    """

    with open("/etc/resolv.conf", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("nameserver"):
                return line.split()[1].strip()
    raise RuntimeError("Unable to determine Windows host IP address")


def ensure_host_ollama(host_ip: str, timeout: int = 60) -> None:
    """Verify that Ollama is reachable on the Windows host."""

    url = f"http://{host_ip}:11434/api/version"
    print(f"Checking for Ollama on Windows host at {url}...", flush=True)
    for _ in range(timeout):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except urllib.error.URLError:
            time.sleep(1)
    raise RuntimeError(
        "Ollama server on Windows host not responding; install and run Ollama on Windows so it can access the GPU",
    )


def ensure_ffmpeg() -> None:
    """Ensure FFmpeg is installed via apt."""
    print("Checking for FFmpeg...", flush=True)
    if shutil.which("ffmpeg") is None:
        _run(["sudo", "apt-get", "update"])
        _run(["sudo", "apt-get", "install", "-y", "ffmpeg"])
    else:
        print("FFmpeg already present", flush=True)


def ensure_app_user() -> Path:
    """Create the dedicated application user if needed."""
    print(f"Ensuring application user '{APP_USER}' exists...", flush=True)
    try:
        pwd.getpwnam(APP_USER)
        print(f"User '{APP_USER}' already present", flush=True)
    except KeyError:
        _run(["useradd", "--create-home", "--shell", "/bin/bash", APP_USER])
    return Path(f"/home/{APP_USER}")


def ensure_openwebui() -> None:
    """Install Open WebUI using pip."""
    print("Installing/upgrading Open WebUI...", flush=True)
    _run([
        "sudo",
        "-H",
        "-u",
        APP_USER,
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--user",
        "open-webui",
    ])


def create_scripts(home: Path) -> None:
    """Create start/stop scripts in the application user's home directory."""
    print("Creating helper scripts...", flush=True)
    home.mkdir(parents=True, exist_ok=True)
    start = home / "start-tomex.sh"
    start.write_text(
        "#!/bin/bash\n"
        "WIN_HOST=$(awk '/nameserver/ {print $2; exit}' /etc/resolv.conf)\n"
        "export OLLAMA_HOST=http://$WIN_HOST:11434\n"
        "PATH=\"$HOME/.local/bin:$PATH\"\n"
        "open-webui --host 0.0.0.0 &\n"
    )
    start.chmod(0o755)
    shutil.chown(start, APP_USER, APP_USER)

    stop = home / "stop-tomex.sh"
    stop.write_text(
        "#!/bin/bash\n"
        "pkill -f 'open-webui'\n"
    )
    stop.chmod(0o755)
    shutil.chown(stop, APP_USER, APP_USER)


def start_stack(home: Path) -> None:
    """Start the Tomex stack using the helper script."""
    print("Starting Tomex...", flush=True)
    start = home / "start-tomex.sh"
    _run(["sudo", "-u", APP_USER, str(start)])


def install(argv: list[str] | None = None) -> None:
    """Install the Tomex stack inside the current WSL distribution."""
    parser = argparse.ArgumentParser(description="Install Tomex inside WSL")
    parser.parse_args(argv)

    host_ip = _windows_host_ip()
    ensure_host_ollama(host_ip)
    ensure_ffmpeg()
    home = ensure_app_user()
    ensure_openwebui()
    create_scripts(home)
    start_stack(home)


if __name__ == "__main__":
    try:
        install()
    except Exception as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
