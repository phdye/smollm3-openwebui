#!/usr/bin/env python3
# Idempotent, restartable unattended installer for Windows 11 that sets up:
# - Ollama (Windows zip)
# - SmolLM3-3B (GGUF Q4_K_M) + Modelfile => model name 'smollm3-local'
# - Open WebUI (Docker preferred; fallback to pip+venv)
#
# Logging:
# - Writes detailed logs (including ALL stdout/stderr from invoked commands)
#   to %LOCALAPPDATA%\smollm3_stack\logs\install-YYYYMMDD-HHMMSS.log
# - Also writes logs\latest-log.txt containing the absolute path to the latest log
#
# Features:
# - Resumable downloads (.part + HTTP Range)
# - Skips already-completed work (no re-downloads, re-extracts, or re-creates)
# - Streams child process output into log ("script(1)"-style)
# - Service-like autostart via Scheduled Task; on access denied, falls back to Startup-folder .cmd
#
# Usage:
#   python install_smollm3_openwebui_unattended.py

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

BASE               = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "smollm3_stack"
DOWNLOADS_DIR      = BASE / "downloads"
OLLAMA_DIR         = BASE / "ollama"
OLLAMA_BIN         = OLLAMA_DIR / "ollama.exe"
OLLAMA_MODELS_DIR  = BASE / "models"
OPENWEBUI_DIR      = BASE / "openwebui"
OPENWEBUI_VENV     = BASE / "openwebui-venv"
LOGS_DIR           = BASE / "logs"

# Global logger
logger = logging.getLogger("smollm3_installer")

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


def get_programs_folder():
    appdata = os.environ.get("APPDATA")
    return (Path(appdata) / r"Microsoft\Windows\Start Menu\Programs") if appdata else None


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


def create_uninstall_shortcut():
    pf = get_programs_folder()
    if not pf:
        return None
    wrapper = pf / "Uninstall SmolLM3 Open-WebUI.cmd"
    script = Path(__file__).resolve()
    try:
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        with open(wrapper, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write(f'cd /d "{script.parent}"\n')
            f.write(f'"{sys.executable}" "{script}" --uninstall\n')
        logger.info(f"- Created Start Menu uninstall shortcut: {wrapper}")
        return wrapper
    except Exception as e:
        logger.warning(f"Could not create uninstall shortcut: {e}")
        return None


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


def uninstall():
    log_file = setup_logging()
    logger.info("Uninstalling SmolLM3 Open-WebUI stack ...")

    # Remove scheduled tasks (ignore errors)
    for task in ["Ollama Serve", "Open WebUI (Docker)", "Open WebUI"]:
        try:
            run(["schtasks", "/Delete", "/TN", task, "/F"], check=False)
        except Exception as e:
            logger.warning(f"Could not delete task '{task}': {e}")

    # Remove Startup .cmd files
    sf = get_startup_folder()
    if sf:
        for name in ["Ollama Serve", "Open WebUI (Docker)", "Open WebUI"]:
            p = sf / f"{name.replace(' ','_')}.cmd"
            if p.exists():
                try:
                    p.unlink()
                    logger.info(f"- Removed Startup .cmd: {p}")
                except Exception:
                    pass

    # Remove uninstall shortcut
    pf = get_programs_folder()
    if pf:
        p = pf / "Uninstall SmolLM3 Open-WebUI.cmd"
        if p.exists():
            try:
                p.unlink()
                logger.info(f"- Removed uninstall shortcut: {p}")
            except Exception:
                pass

    # Remove install directory
    if BASE.exists():
        shutil.rmtree(BASE, ignore_errors=True)
        logger.info(f"- Removed {BASE}")

    logger.info(f"- Log saved to: {log_file}")
    logger.info("✅ Uninstall complete.")

# -----------------------------
# Main
# -----------------------------

def main():
    log_file = setup_logging()
    logger.info(f"Install root: {BASE}")

    for p in [BASE, DOWNLOADS_DIR, OLLAMA_DIR, OLLAMA_MODELS_DIR, OPENWEBUI_DIR]:
        p.mkdir(parents=True, exist_ok=True)

    create_uninstall_shortcut()

    # 1) Ollama
    ensure_ollama_installed()
    ensure_ollama_running_and_autostart()

    # 2) SmolLM3 model
    ensure_smollm3_model()

    # 3) Open WebUI
    if docker_available():
        ensure_openwebui_docker()
    else:
        ensure_openwebui_pip()

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
    if "--uninstall" in sys.argv:
        uninstall()
    else:
        main()
