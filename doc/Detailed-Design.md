# Detailed Design

## Overview
Tomex is an unattended installer that assembles a local language model stack
comprised of [Ollama](https://ollama.ai), the SmolLM3‑3B model, [Open WebUI](https://github.com/open-webui/open-webui) and
FFmpeg.  The project targets Windows but supports multiple back‑ends for running
Open WebUI (native Windows, WSL, Docker, or a Python virtual environment).  Each
run is idempotent: previously completed work is skipped, downloads resume, and
external processes are restarted when necessary.

The code base is intentionally lightweight.  The repository contains a thin
wrapper (`tomex-installer.py`) and a set of back‑end specific installer modules
under `installers/`.

## Repository Layout
```
smollm3-openwebui/
├── tomex-installer.py          # Front end that dispatches to a back‑end
├── installers/                 # Back‑end installers
│   ├── windows.py              # Windows 11 native installer
│   ├── wsl.py                  # Runs fully inside a WSL distribution
│   ├── docker.py               # Uses Docker containers for Ollama and WebUI
│   └── pip_installer.py        # Pure Python virtual environment installer
└── doc/                        # Documentation
```

## Top‑Level Wrapper: `tomex-installer.py`
`tomex-installer.py` selects which back‑end to run based on the `--backend`
argument or the host platform.  Back‑ends are defined in the `BACKENDS` mapping
and imported by module name【F:tomex-installer.py†L19-L24】.  After parsing
arguments the wrapper either invokes the module directly or, for the WSL
backend on Windows, spawns `wsl.exe` to execute it inside a distribution
while also creating Start Menu shortcuts for the generated helper scripts
(`start-tomex.cmd`/`stop-tomex.cmd`)【F:tomex-installer.py†L27-L56】【F:tomex-installer.py†L59-L93】.

## Common Design Concepts in Installers
All installers share several ideas:

### Paths and Constants
The Windows installer defines canonical locations for downloads, executables and
logs under `%LOCALAPPDATA%\tomex`【F:installers/windows.py†L37-L57】.  Other
installers follow the same convention where applicable.

### Logging
`setup_logging()` in the Windows module configures both console and file
logging.  Logs are timestamped and the latest log file path is written to
`logs/latest-log.txt`【F:installers/windows.py†L66-L91】.  The `run()` helper wraps
`subprocess.Popen` to stream all output into the logger, producing detailed
records of every command executed【F:installers/windows.py†L99-L138】.

### Idempotency and Resumable Downloads
The `resumable_download()` function performs HTTP downloads that can resume
after interruption.  It uses a `.part` file, HEAD requests to determine remote
size, and `Range` headers to continue partial downloads【F:installers/windows.py†L327-L399】.
Many installer steps check for existing files or running services before doing
work, allowing the entire script to be re‑run safely.

### Start/Stop Scripts and Autostart
After installation each back‑end generates helper scripts in the user's home
folder.  For Windows these are `start-tomex.cmd` and `stop-tomex.cmd` with
matching `.sh` wrappers for WSL usage【F:installers/windows.py†L213-L276】.
`try_create_logon_task()` attempts to register a Scheduled Task that runs at
logon; if creation fails a Startup‑folder script is used as a fallback【F:installers/windows.py†L152-L186】.
`ensure_start_menu_shortcuts()` places Start Menu entries that point to the
scripts and to the web interface【F:installers/windows.py†L278-L325】.

## Windows Back‑End (`installers/windows.py`)
The Windows installer is the most feature rich because it must orchestrate the
entire stack on the host system.

### Ollama
1. **Installation** – `ensure_ollama_installed()` downloads a zipped release,
   extracts it, and adds the directory to the user PATH【F:installers/windows.py†L400-L438】.
2. **Startup** – `ensure_ollama_running_and_autostart()` launches `ollama serve`
   in the background if the API port is not already open and registers a
   Scheduled Task for automatic start【F:installers/windows.py†L442-L473】.

### SmolLM3 Model
`ensure_smollm3_model()` downloads the GGUF model file, writes a Modelfile with
inference parameters and imports the model into Ollama under the name
`smollm3-local` when absent【F:installers/windows.py†L475-L516】.

### Open WebUI Backends
Depending on configuration the installer provisions one of three back ends:
- **Docker** – `ensure_openwebui_docker()` runs a container and registers a task
  to start it on logon【F:installers/windows.py†L547-L573】.
- **WSL** – `ensure_openwebui_wsl()` installs Open WebUI inside a specified
  distribution, guarantees `pip`, `venv`, and FFmpeg, launches the service, and
  sets up autostart via a Scheduled Task【F:installers/windows.py†L576-L662】.
- **pip/venv** – `ensure_openwebui_pip()` creates a virtual environment,
  installs Open WebUI, registers an autostart task, and starts the server if it
  is not already running【F:installers/windows.py†L674-L710】.

### FFmpeg
`ensure_ffmpeg_on_host()` installs FFmpeg using `winget` when necessary, or adds
its location to the PATH.  When running Docker it instead ensures FFmpeg exists
inside the Open WebUI container via `ensure_ffmpeg_in_container()`【F:installers/windows.py†L716-L768】.

### Main Control Flow
The `install()` function orchestrates installation:
1. Set up logging and directories.
2. Install and start Ollama.
3. Download/import the SmolLM3 model.
4. Provision Open WebUI using WSL, Docker or pip.
5. Create start/stop scripts and Start Menu shortcuts.
6. Print connection information for the user【F:installers/windows.py†L775-L839】.

## WSL Back‑End (`installers/wsl.py`)
The WSL installer runs entirely inside a distribution and performs a linear
sequence of steps:
1. Create a dedicated `tomex` system user with the home directory `/opt/tomex`
   (`ensure_tomex_user`).
2. Install Ollama if missing (`ensure_ollama`).
3. Wait for the Ollama API and pull the `smollm3:3b` model (`ensure_model`).
4. Install FFmpeg via `apt` (`ensure_ffmpeg`).
5. Install Open WebUI for the `tomex` user using `pip` (`ensure_openwebui`).
6. Generate `start-tomex.sh` and `stop-tomex.sh` in `/opt/tomex`
   (`create_scripts`).
7. Launch the stack as the `tomex` user (`start_stack`)【F:installers/wsl.py†L1-L116】.

Each command is echoed before execution so that the user sees a blow‑by‑blow log
of what happened.

## Docker Back‑End (`installers/docker.py`)
The Docker installer provisions both services as containers:
1. Verify the Docker CLI is available (`ensure_docker`).
2. Create or start an `ollama` container and pull the SmolLM3 model.
3. Create or start an `open-webui` container and install FFmpeg inside it.
4. Create helper scripts to start or stop the containers for both Windows and
   Unix shells (`create_scripts`).
5. Expose Open WebUI on port 3000 and Ollama on 11434 by relying on the default
   container mappings【F:installers/docker.py†L1-L109】.

## Python Virtual Environment Back‑End (`installers/pip_installer.py`)
This back‑end avoids Docker and WSL entirely:
1. Use `winget` to install Ollama and FFmpeg when absent.
2. Pull the `smollm3:3b` model via `ollama pull`.
3. Create a dedicated virtual environment (`tomex-venv`) and install Open WebUI
   into it (`ensure_openwebui`).
4. Generate platform‑specific start/stop scripts referencing the virtual
   environment (`create_scripts`).
5. No background services are automatically started; the scripts are intended
   for manual invocation【F:installers/pip_installer.py†L1-L96】.

## Interaction of Components
All back‑ends aim to provide two running services:
- **Ollama** on port 11434 serving the SmolLM3‑3B model under the name
  `smollm3-local`.
- **Open WebUI** on port 3000 connecting to the Ollama API.
Helper scripts provide a consistent user experience for starting and stopping
these services across environments.

## Reimplementation Notes
A clean reimplementation should maintain the following behaviours:
- Idempotent steps that skip work when already complete.
- Detailed logging of every external command.
- Resumable downloads for large assets.
- Creation of helper scripts and autostart integration on Windows.
- Separation of concerns via modular back‑ends selected by a thin wrapper.

By following the structure above a junior developer should be able to recreate
the Tomex installer from scratch while preserving its key characteristics.

