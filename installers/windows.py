#!/usr/bin/env python3
# Idempotent, restartable unattended installer for Windows 11 that sets up:
# - Ollama (Windows zip)
# - SmolLM3-3B (GGUF Q4_K_M) + Modelfile => model name 'smollm3-local'
# - Open WebUI (Docker preferred; fallback to pip+venv)
#
# Logging:
# - Writes detailed logs (including ALL stdout/stderr from invoked commands)
#   to %LOCALAPPDATA%\tomex\logs\install-YYYYMMDD-HHMMSS.log
# - Also writes logs\latest-log.txt containing the absolute path to the latest log
#
# Features:
# - Resumable downloads (.part + HTTP Range)
# - Skips already-completed work (no re-downloads, re-extracts, or re-creates)
# - Streams child process output into log ("script(1)"-style)
# - Service-like autostart via Scheduled Task; on access denied, falls back to Startup-folder .cmd
#
# Usage:
#   python tomex-installer.py --backend windows [--wsl <distro-name>]

import os
import sys
import json
import time
import shutil
import zipfile
import subprocess
import platform
import socket
import urllib.request
import urllib.error
import logging
import argparse
from pathlib import Path
from types import SimpleNamespace

# -----------------------------
# Settings (safe defaults)
# -----------------------------
OPENWEBUI_PORT = 3000
OLLAMA_PORT    = 11434

MODEL_REPO  = "ggml-org/SmolLM3-3B-GGUF"
MODEL_FILE  = "SmolLM3-Q4_K_M.gguf"  # ~1.9 GB — good for 4 GB VRAM
MODEL_NAME  = "smollm3-local"
NUM_CTX     = 8192
NUM_THREAD  = max(4, os.cpu_count() or 8)
NUM_GPU     = 8

BASE               = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "tomex"
DOWNLOADS_DIR      = BASE / "downloads"
OLLAMA_DIR         = BASE / "ollama"
OLLAMA_BIN         = OLLAMA_DIR / "ollama.exe"
OLLAMA_MODELS_DIR  = BASE / "models"
OPENWEBUI_DIR      = BASE / "openwebui"
OPENWEBUI_VENV     = BASE / "openwebui-venv"
LOGS_DIR           = BASE / "logs"

# Global logger
logger = logging.getLogger("tomex_installer")

# -----------------------------
# Logging & utility helpers
# -----------------------------

def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    log_file = LOGS_DIR / f"install-{ts}.log"

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Pointer file for convenience
    try:
        (LOGS_DIR / "latest-log.txt").write_text(str(log_file), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Unable to write latest-log.txt: {e}")

    logger.info(f"Logging to: {log_file}")
    return log_file


def ensure_dirs():
    for p in [BASE, DOWNLOADS_DIR, OLLAMA_DIR, OLLAMA_MODELS_DIR, OPENWEBUI_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def run(cmd, check=True, shell=False, env=None, cwd=None):
    """
    Run a command while streaming ALL stdout/stderr into the logger (script(1)-style).
    Returns a CompletedProcess-like object with returncode, stdout (captured), and stderr (empty; merged into stdout).
    """
    if isinstance(cmd, list):
        cmd_display = " ".join(cmd)
    else:
        cmd_display = cmd
    logger.info(f"$ {cmd_display}")

    # Use text mode with line buffering; merge stderr into stdout
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    collected = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            collected.append(line + "\n")
            logger.info(line)
    finally:
        ret = proc.wait()

    if check and ret != 0:
        # Include last 50 lines for context
        tail = ''.join(collected[-50:])
        raise subprocess.CalledProcessError(ret, cmd, output=tail)

    return SimpleNamespace(returncode=ret, stdout=''.join(collected), stderr='')


def in_path(exe):
    path = shutil.which(exe)
    logger.debug(f"which {exe} -> {path}")
    return path is not None


def get_startup_folder():
    appdata = os.environ.get("APPDATA")
    return (Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Startup") if appdata else None


def create_startup_cmd(name: str, command: str, workdir: Path=None):
    sf = get_startup_folder()
    if not sf:
        return None
    wrapper = sf / f"{name.replace(' ','_')}.cmd"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        if workdir:
            f.write(f'cd /d "{workdir}"\n')
        f.write(command + "\n")
    logger.info(f"- Created Startup .cmd: {wrapper}")
    return wrapper


def try_create_logon_task(name: str, command: str, workdir: Path=None):
    # Idempotent: /F overwrites. If denied, fallback to Startup folder.
    wrapper = BASE / f"{name.replace(' ', '_').lower()}.cmd"
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        if workdir:
            f.write(f'cd /d "{workdir}"\n')
        f.write(command + "\n")
    try:
        run(["schtasks","/Create","/TN",name,"/TR",f'"{wrapper}"',"/SC","ONLOGON","/F"], check=True)
        logger.info(f"- Created/updated scheduled task: {name}")
        return "task"
    except subprocess.CalledProcessError as e:
        msg = (e.output or '').strip()
        logger.warning(f"Could not create scheduled task '{name}': {msg or 'Unknown error'}")
        sfw = create_startup_cmd(name, command, workdir)
        if sfw:
            logger.info(f"- Falling back to Startup folder: {sfw}")
            return "startup"
        return None


def port_open(host: str, port: int, timeout=1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def wait_for_http(url: str, timeout_s=180):
    logger.info(f"- Waiting for HTTP: {url}")
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                if 200 <= r.status < 500:
                    logger.info(f"- HTTP ready: {url} (status {r.status})")
                    return True
        except Exception:
            time.sleep(2)
    logger.warning(f"! Timeout waiting for {url}")
    return False


def create_start_stop_scripts(mode: str, distro: str | None):
    """Create start/stop scripts for Windows and WSL."""
    start_cmd = BASE / "start-tomex.cmd"
    stop_cmd = BASE / "stop-tomex.cmd"

    if mode == "wsl":
        start_lines = [
            "@echo off",
            f"start \"\" \"{OLLAMA_BIN}\" serve",
            (
                f"wsl -d {distro} sh -lc \"env OLLAMA_BASE_URL=\\\"http://localhost:{OLLAMA_PORT}\\\" "
                f"~/.open-webui-venv/bin/open-webui serve --host 0.0.0.0 --port {OPENWEBUI_PORT}\""
            ),
        ]
        stop_lines = [
            "@echo off",
            "taskkill /IM ollama.exe /F >nul 2>&1",
            f"wsl -d {distro} sh -lc \"pkill -f open-webui\"",
        ]
    elif mode == "docker":
        start_lines = [
            "@echo off",
            f"start \"\" \"{OLLAMA_BIN}\" serve",
            "docker start open-webui",
        ]
        stop_lines = [
            "@echo off",
            "docker stop open-webui >nul 2>&1",
            "taskkill /IM ollama.exe /F >nul 2>&1",
        ]
    else:  # pip
        ow_exe = OPENWEBUI_VENV / "Scripts" / "open-webui.exe"
        start_lines = [
            "@echo off",
            f"start \"\" \"{OLLAMA_BIN}\" serve",
            f"\"{ow_exe}\" serve --host 127.0.0.1 --port {OPENWEBUI_PORT}",
        ]
        stop_lines = [
            "@echo off",
            "taskkill /IM open-webui.exe /F >nul 2>&1",
            "taskkill /IM ollama.exe /F >nul 2>&1",
        ]

    for path, lines in [(start_cmd, start_lines), (stop_cmd, stop_lines)]:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            logger.info(f"- Created script: {path}")
        except Exception as e:
            logger.warning(f"Could not write {path}: {e}")

    # WSL wrappers
    start_sh = BASE / "start-tomex.sh"
    stop_sh = BASE / "stop-tomex.sh"
    for src, dst in [(start_cmd, start_sh), (stop_cmd, stop_sh)]:
        try:
            with open(dst, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
                f.write(f"cmd.exe /c \"{src}\"\n")
            os.chmod(dst, 0o755)
            logger.info(f"- Created script: {dst}")
        except Exception as e:
            logger.warning(f"Could not write {dst}: {e}")


def ensure_start_menu_shortcuts(distro: str | None):
    """Create Start Menu folder and shortcuts for Tomex."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        logger.warning("APPDATA not set; cannot create Start Menu shortcuts")
        return

    sm_dir = Path(appdata) / r"Microsoft\Windows\Start Menu\Programs\Tomex"
    sm_dir.mkdir(parents=True, exist_ok=True)

    # Browser shortcut to the Web UI
    url_file = sm_dir / "Open WebUI.url"
    try:
        url_file.write_text(
            f"[InternetShortcut]\nURL=http://localhost:{OPENWEBUI_PORT}\n",
            encoding="utf-8",
        )
        logger.info(f"- Created Start Menu shortcut: {url_file}")
    except Exception as e:
        logger.warning(f"Could not create shortcut {url_file}: {e}")

    # Wrappers to start/stop scripts
    start_cmd = BASE / "start-tomex.cmd"
    stop_cmd = BASE / "stop-tomex.cmd"
    start_link = sm_dir / "Start Tomex.cmd"
    stop_link = sm_dir / "Stop Tomex.cmd"
    for src, dst in [(start_cmd, start_link), (stop_cmd, stop_link)]:
        try:
            with open(dst, "w", encoding="utf-8") as f:
                f.write(f"@echo off\n\"{src}\"\n")
            logger.info(f"- Created Start Menu shortcut: {dst}")
        except Exception as e:
            logger.warning(f"Could not create shortcut {dst}: {e}")

    if distro:
        cmd_file = sm_dir / "Open WebUI (WSL).cmd"
        cmd = (
            f'wsl -d {distro} sh -lc "env OLLAMA_BASE_URL=\\"http://localhost:{OLLAMA_PORT}\\" '
            f'~/.open-webui-venv/bin/open-webui serve --host 0.0.0.0 --port {OPENWEBUI_PORT}"'
        )
        try:
            with open(cmd_file, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write(cmd + "\n")
            logger.info(f"- Created Start Menu shortcut: {cmd_file}")
        except Exception as e:
            logger.warning(f"Could not create shortcut {cmd_file}: {e}")


def head_content_length(url: str) -> int | None:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            cl = r.headers.get("Content-Length")
            return int(cl) if cl and cl.isdigit() else None
    except Exception:
        return None


def _stream_copy(resp, out_file, total, start):
    read = start
    chunk = 1024 * 1024
    last_pct = -1
    while True:
        b = resp.read(chunk)
        if not b:
            break
        out_file.write(b)
        read += len(b)
        if total:
            pct = int(read * 100 / total)
            if pct == 100 or pct >= last_pct + 5:
                logger.info(f"  {pct}% ({read//(1024*1024)}MB/{total//(1024*1024)}MB)")
                last_pct = pct


def resumable_download(url: str, dest: Path, desc: str):
    """
    Idempotent + restartable download:
    - if dest exists and matches remote size -> skip
    - resumes into dest.part using HTTP Range
    - if server doesn't support Range, falls back to full re-download to temp then replaces
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = head_content_length(url)  # okay if None
    part = dest.with_suffix(dest.suffix + ".part")

    # Already complete?
    if dest.exists():
        if total is None:
            logger.info(f"- {desc} exists; skipping (size unknown).")
            return
        if dest.stat().st_size == total:
            logger.info(f"- {desc} already complete; skipping.")
            return
        else:
            # Move incomplete to .part
            if part.exists():
                if dest.stat().st_size > part.stat().st_size:
                    try: part.unlink()
                    except: pass
                    dest.rename(part)
                else:
                    dest.unlink()
            else:
                dest.rename(part)

    already = part.stat().st_size if part.exists() else 0
    if total is not None and already > total:
        part.unlink(missing_ok=True)
        already = 0

    headers = {"User-Agent":"Mozilla/5.0"}
    if already and total and already < total:
        headers["Range"] = f"bytes={already}-"

    logger.info(f"- Starting {desc}: {url}")
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as r, open(part, "ab" if already else "wb") as f:
            # If server ignored Range and returned 200 while we had partial, start fresh
            if already and getattr(r, "status", 200) == 200:
                f.close()
                part.unlink(missing_ok=True)
                already = 0
                logger.info("  (server ignored Range; falling back to full download)")
                req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req) as rr, open(part, "wb") as ff:
                    _stream_copy(rr, ff, total, 0)
            else:
                _stream_copy(r, f, total, already)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # Range not satisfiable — assume complete
            logger.info("  Server reports 416 (Range not satisfiable) — assuming already complete.")
        else:
            logger.error(f"  HTTP error during download: {e}")
            raise

    if total is not None and part.exists() and part.stat().st_size < total:
        raise RuntimeError(f"{desc} incomplete ({part.stat().st_size} < {total}). Re-run to resume.")
    if part.exists():
        os.replace(part, dest)
    logger.info(f"- Saved to {dest}")


def add_to_user_path(dirpath: Path):
    current = os.environ.get("PATH","")
    parts = [p.strip() for p in current.split(";") if p.strip()]
    if str(dirpath) in parts:
        logger.info(f"- PATH already contains {dirpath}")
        return
    try:
        run(["setx","PATH", current + ";" + str(dirpath)], check=True)
        logger.info(f"- Added to PATH (user): {dirpath}")
    except Exception as e:
        logger.warning(f"! Failed to add PATH entry: {e}")

# -----------------------------
# Ollama
# -----------------------------

def ensure_ollama_installed():
    if OLLAMA_BIN.exists() or in_path("ollama"):
        logger.info("- Ollama already present.")
        return
    zip_url = "https://github.com/ollama/ollama/releases/download/v0.11.4/ollama-windows-amd64.zip"
    zpath = DOWNLOADS_DIR / "ollama-windows-amd64.zip"
    resumable_download(zip_url, zpath, "Ollama CLI download")
    logger.info(f"- Extracting {zpath.name} -> {OLLAMA_DIR}")
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(OLLAMA_DIR)
    add_to_user_path(OLLAMA_DIR)
    logger.info(f"- Ollama installed to {OLLAMA_DIR}")


def ensure_ollama_running_and_autostart():
    if port_open("127.0.0.1", OLLAMA_PORT):
        logger.info("- Ollama API already up.")
    else:
        binp = str(OLLAMA_BIN if OLLAMA_BIN.exists() else (shutil.which("ollama") or OLLAMA_BIN))
        logger.info("- Starting ollama serve (background)")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        env = {**os.environ, "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR)}
        try:
            subprocess.Popen([binp, "serve"], cwd=OLLAMA_DIR, env=env,
                             creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
        except Exception as e:
            logger.error(f"! Failed to start ollama serve: {e}")

    binp = str(OLLAMA_BIN if OLLAMA_BIN.exists() else (shutil.which("ollama") or OLLAMA_BIN))
    try_create_logon_task("Ollama Serve", f'"{binp}" serve', workdir=OLLAMA_DIR)

    wait_for_http(f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", timeout_s=180)


def model_exists(name: str) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{OLLAMA_PORT}/api/tags", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        for m in data.get("models", []):
            if m.get("name","").split(":")[0] == name:
                return True
    except Exception:
        pass
    return False


def ensure_smollm3_model():
    url = f"https://huggingface.co/{MODEL_REPO}/resolve/main/{MODEL_FILE}?download=true"
    gguf_path = OLLAMA_MODELS_DIR / MODEL_FILE
    total = head_content_length(url)
    if gguf_path.exists() and (total is None or gguf_path.stat().st_size == total):
        logger.info(f"- {MODEL_FILE} already complete; skipping download.")
    else:
        resumable_download(url, gguf_path, f"{MODEL_FILE} (SmolLM3 GGUF)")

    modelfile = OLLAMA_MODELS_DIR / "Modelfile"
    desired = "\n".join([
        f"FROM .\\{MODEL_FILE}",
        f"PARAMETER num_ctx {NUM_CTX}",
        f"PARAMETER num_thread {NUM_THREAD}",
        f"PARAMETER num_gpu {NUM_GPU}",
        "PARAMETER temperature 0.3",
        "",
    ])
    write = True
    if modelfile.exists():
        try:
            if modelfile.read_text(encoding="utf-8") == desired:
                write = False
        except Exception:
            pass
    if write:
        modelfile.write_text(desired, encoding="utf-8")
        logger.info(f"- Wrote Modelfile -> {modelfile}")
    else:
        logger.info("- Modelfile already up to date.")

    if model_exists(MODEL_NAME):
        logger.info(f"- Ollama model '{MODEL_NAME}' already exists; skipping create.")
        return

    binp = str(OLLAMA_BIN if OLLAMA_BIN.exists() else (shutil.which("ollama") or OLLAMA_BIN))
    logger.info(f"- Importing model into Ollama as '{MODEL_NAME}' ...")
    try:
        env = {**os.environ, "OLLAMA_MODELS": str(OLLAMA_MODELS_DIR)}
        run([binp, "create", MODEL_NAME, "-f", str(modelfile)], check=True, env=env)
        logger.info("- Model imported.")
    except subprocess.CalledProcessError as e:
        logger.error(f"! Failed to create model: {e.output}")

# -----------------------------
# Open WebUI
# -----------------------------

def docker_available():
    try:
        run(["docker","--version"])  # log output too
        return True
    except Exception:
        return False


def wsl_available() -> bool:
    return shutil.which("wsl") is not None


def ensure_openwebui_docker():
    def container_exists():
        cp = subprocess.run(["docker","ps","-a","--filter","name=open-webui","--format","{{.Names}}"],
                            capture_output=True, text=True)
        return "open-webui" in (cp.stdout or "")
    def container_running():
        cp = subprocess.run(["docker","ps","--filter","name=open-webui","--format","{{.Names}}"],
                            capture_output=True, text=True)
        return "open-webui" in (cp.stdout or "")

    if container_exists():
        if not container_running():
            run(["docker","start","open-webui"], check=False)
        logger.info(f"- Open WebUI (Docker) ensured at http://localhost:{OPENWEBUI_PORT}")
    else:
        env_url = f"http://host.docker.internal:{OLLAMA_PORT}"
        logger.info("- Launching Open WebUI (Docker) ...")
        run([
            "docker","run","-d","--name","open-webui",
            "-p", f"{OPENWEBUI_PORT}:8080",
            "-e", f"OLLAMA_BASE_URL={env_url}",
            "--restart","unless-stopped",
            "open-webui/open-webui:latest",
        ], check=True)
        logger.info(f"- Open WebUI container created on port {OPENWEBUI_PORT}")

    try_create_logon_task("Open WebUI (Docker)", "docker start open-webui")


def ensure_openwebui_wsl(distro: str):
    if not wsl_available():
        logger.error("wsl.exe not found; install the Windows Subsystem for Linux feature.")
        sys.exit(1)
    # wsl.exe emits UTF-16 output; without decoding, distro names contain nulls
    cp = subprocess.run(
        ["wsl", "-l", "-q"], capture_output=True, text=True, encoding="utf-16-le"
    )
    dlist = [d.strip() for d in (cp.stdout or "").splitlines()]
    if distro not in dlist:
        logger.error(f"WSL distro '{distro}' not found. Available: {dlist}")
        sys.exit(1)

    def wsl(cmd: str, check: bool = True, as_root: bool = False):
        base = ["wsl", "-d", distro]
        if as_root:
            base += ["-u", "root"]
        base += ["sh", "-lc", cmd]
        return run(base, check=check)

    logger.info(f"- Ensuring Open WebUI inside WSL distro '{distro}' ...")

    # Ensure pip
    res = wsl("python3 -m pip --version >/dev/null 2>&1", check=False)
    if res.returncode != 0:
        res = wsl("python3 -m ensurepip --upgrade >/dev/null 2>&1", check=False)
    if res.returncode != 0:
        wsl(
            "(command -v apt >/dev/null 2>&1 && apt update && apt install -y python3-pip) || "
            "(command -v apk >/dev/null 2>&1 && apk add --no-cache py3-pip) || "
            "(command -v dnf >/dev/null 2>&1 && dnf install -y python3-pip)",
            as_root=True,
        )

    # Install Open WebUI into a dedicated virtual environment
    venv = "$HOME/.open-webui-venv"
    res = wsl(f"[ -d {venv} ] || python3 -m venv {venv}", check=False)
    if res.returncode != 0:
        wsl(
            "(command -v apt >/dev/null 2>&1 && apt update && apt install -y python3-venv) || "
            "(command -v apk >/dev/null 2>&1 && apk add --no-cache py3-virtualenv) || "
            "(command -v dnf >/dev/null 2>&1 && dnf install -y python3-venv)",
            as_root=True,
        )
        wsl(f"python3 -m venv {venv}")
    # Some distributions build Python without ensurepip in the venv; bootstrap pip if missing.
    res = wsl(f"[ -x {venv}/bin/pip ]", check=False)
    if res.returncode != 0:
        res = wsl(f"{venv}/bin/python -m ensurepip --upgrade", check=False)
        if res.returncode != 0:
            wsl(
                f"(command -v curl >/dev/null 2>&1 && curl -sSf https://bootstrap.pypa.io/get-pip.py | {venv}/bin/python) || "
                f"(command -v wget >/dev/null 2>&1 && wget -qO- https://bootstrap.pypa.io/get-pip.py | {venv}/bin/python)",
            )
    wsl(f"{venv}/bin/pip install --upgrade pip", check=False)
    wsl(
        f"{venv}/bin/pip show open-webui >/dev/null 2>&1 || "
        f"{venv}/bin/pip install open-webui"
    )

    # Ensure ffmpeg (root only when missing)
    res = wsl("command -v ffmpeg >/dev/null 2>&1", check=False)
    if res.returncode != 0:
        wsl(
            "(command -v apt >/dev/null 2>&1 && apt update && apt install -y ffmpeg) || "
            "(command -v apk >/dev/null 2>&1 && apk add --no-cache ffmpeg) || "
            "(command -v dnf >/dev/null 2>&1 && dnf install -y ffmpeg)",
            check=False,
            as_root=True,
        )
    cmd = [
        "wsl", "-d", distro, "sh", "-lc",
        f'env OLLAMA_BASE_URL="http://localhost:{OLLAMA_PORT}" '
        f'{venv}/bin/open-webui serve --host 0.0.0.0 --port {OPENWEBUI_PORT}'
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("- Launched Open WebUI inside WSL")
    except Exception as e:
        logger.warning(f"Could not launch Open WebUI: {e}")

    try_create_logon_task(
        "Open WebUI (WSL)",
        f'wsl -d {distro} sh -lc "env OLLAMA_BASE_URL=\\"http://localhost:{OLLAMA_PORT}\\" {venv}/bin/open-webui serve --host 0.0.0.0 --port {OPENWEBUI_PORT}"'
    )
    logger.info(f"- Open WebUI (WSL) ensured at http://localhost:{OPENWEBUI_PORT}")


def py_exe_preference():
    for cand in (["py","-3.11"], ["py","-3.12"], [sys.executable]):
        try:
            run(cand + ["--version"])  # log output
            return cand
        except Exception:
            continue
    return [sys.executable]


def ensure_openwebui_pip():
    if port_open("127.0.0.1", OPENWEBUI_PORT):
        logger.info(f"- Open WebUI already listening on {OPENWEBUI_PORT}; skipping start.")
        return

    vpy = OPENWEBUI_VENV / "Scripts" / "python.exe"
    ow_exe = OPENWEBUI_VENV / "Scripts" / "open-webui.exe"

    if not vpy.exists():
        logger.info("- Installing Open WebUI via pip into venv ...")
        OPENWEBUI_VENV.mkdir(parents=True, exist_ok=True)
        py = py_exe_preference()
        run(py + ["-m","venv", str(OPENWEBUI_VENV)], check=True)
        run([str(vpy), "-m", "pip", "install", "--upgrade", "pip", "wheel"], check=True)
        run([str(vpy), "-m", "pip", "install", "open-webui"], check=True)
    else:
        logger.info("- Open WebUI venv already present.")

    try_create_logon_task(
        "Open WebUI",
        f'"{ow_exe}" serve --host 127.0.0.1 --port {OPENWEBUI_PORT}',
        workdir=OPENWEBUI_DIR
    )

    if not port_open("127.0.0.1", OPENWEBUI_PORT):
        logger.info("- Starting Open WebUI (pip) now ...")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        env = {**os.environ, "OLLAMA_BASE_URL": f"http://127.0.0.1:{OLLAMA_PORT}"}
        try:
            subprocess.Popen(
                [str(ow_exe), "serve", "--host", "127.0.0.1", "--port", str(OPENWEBUI_PORT)],
                cwd=OPENWEBUI_DIR, env=env,
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            )
        except Exception as e:
            logger.error(f"! Failed to start Open WebUI (pip): {e}")

# -----------------------------
# FFmpeg (required for audio/video features like STT/TTS)
# -----------------------------

def winget_available() -> bool:
    return shutil.which("winget") is not None


def ffmpeg_in_path() -> bool:
    return shutil.which("ffmpeg") is not None


def ensure_ffmpeg_on_host():
    """Ensure ffmpeg is installed on the Windows host (pip/venv mode)."""
    if ffmpeg_in_path():
        run(["ffmpeg", "-version"], check=False)
        logger.info("- ffmpeg already available on PATH.")
        return

    if winget_available():
        logger.info("- Installing ffmpeg via winget (user scope, silent)...")
        # Accept agreements to keep install unattended; scope=user avoids elevation.
        run([
            "winget","install","--id=Gyan.FFmpeg","-e",
            "--accept-package-agreements","--accept-source-agreements",
            "--scope","user","--silent"
        ], check=False)

        # Re-check PATH
        if ffmpeg_in_path():
            run(["ffmpeg","-version"], check=False)
            logger.info("- ffmpeg installed and found in PATH.")
            return

        # Common location from Gyan.FFmpeg package
        candidate = Path("C:/ffmpeg/bin/ffmpeg.exe")
        if candidate.exists():
            add_to_user_path(candidate.parent)
            logger.info(f"- Added {candidate.parent} to PATH; new shells will see ffmpeg.")
            return

    logger.warning("! ffmpeg still not found. You can install it manually, e.g.: 'winget install --id=Gyan.FFmpeg -e'.")


def ensure_ffmpeg_in_container(container_name: str = "open-webui"):
    """Ensure ffmpeg exists inside the Open WebUI Docker container.
    Tries apt, apk, dnf (depends on base image). Safe to re-run.
    """
    logger.info(f"- Ensuring ffmpeg is present inside Docker container '{container_name}' ...")
    run([
        "docker","exec",container_name,"sh","-lc",
        # If ffmpeg exists, print version. Otherwise try package managers.
        "command -v ffmpeg >/dev/null 2>&1 && ffmpeg -version | head -n1 || "
        "( (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y ffmpeg) || "
        "  (command -v apk >/dev/null 2>&1 && apk add --no-cache ffmpeg) || "
        "  (command -v dnf >/dev/null 2>&1 && dnf install -y ffmpeg) || "
        "  echo 'No known package manager found; ffmpeg not installed.' )"
    ], check=False)

# -----------------------------
# Entrypoint
# -----------------------------

def install(argv: list[str] | None = None) -> None:
    """Run the Windows installer.

    Parameters
    ----------
    argv:
        Optional list of CLI arguments. If omitted, ``sys.argv`` will be
        consulted, enabling the module to be executed directly or invoked via
        the wrapper.
    """

    parser = argparse.ArgumentParser(description="Install Tomex stack")
    parser.add_argument(
        "--wsl",
        metavar="DISTRO",
        help="Use a WSL distribution for Open WebUI instead of Docker/pip",
    )
    args = parser.parse_args(argv)

    log_file = setup_logging()
    logger.info(f"Install root: {BASE}")

    for p in [BASE, DOWNLOADS_DIR, OLLAMA_DIR, OLLAMA_MODELS_DIR, OPENWEBUI_DIR]:
        p.mkdir(parents=True, exist_ok=True)

    # 1) Ollama
    ensure_ollama_installed()
    ensure_ollama_running_and_autostart()

    # 2) SmolLM3 model
    ensure_smollm3_model()

    # 3) Open WebUI + FFmpeg
    if args.wsl:
        ensure_openwebui_wsl(args.wsl)
        mode = "wsl"
    else:
        use_docker = docker_available()
        if use_docker:
            ensure_openwebui_docker()
            ensure_ffmpeg_in_container("open-webui")
            mode = "docker"
        else:
            ensure_ffmpeg_on_host()
            ensure_openwebui_pip()
            mode = "pip"

    # 4) Start/stop scripts and Start Menu shortcuts
    create_start_stop_scripts(mode, args.wsl if args.wsl else None)
    ensure_start_menu_shortcuts(args.wsl if args.wsl else None)

    logger.info("")
    logger.info("✅ All set!")
    logger.info(f"- Open WebUI: http://localhost:{OPENWEBUI_PORT}")
    logger.info(f"- Ollama API: http://localhost:{OLLAMA_PORT}")
    logger.info(f"- Model name: {MODEL_NAME}")
    logger.info(f"- Log saved to: {log_file}")
    print(f"\nLog saved to: {log_file}\n")  # extra explicit notice to console


if __name__ == "__main__":
    if platform.system().lower() != "windows":
        print("This script is intended for Windows 11.")
        sys.exit(1)
    install()
