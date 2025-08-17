# Developer Guide

## Repository Structure
```
smollm3-openwebui/
├── install-smollm3-openwebui-unattended.py
├── doc/
│   ├── User-Guide.md
│   ├── Developer-Guide.md
│   ├── Repo-Support-Plan--Container.md
│   ├── Repo-Support-Plan--WSL.md
│   └── usage.md
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

The installer script is the heart of the project.  Everything else provides documentation or project metadata.

## High Level Flow
`install-smollm3-openwebui-unattended.py` performs the following steps in order:
1. Prepare logging and directory structure.
2. Ensure **Ollama** is installed and running.
3. Download and import the **SmolLM3‑3B** model.
4. Ensure **Open WebUI** is running via Docker, WSL or a Python virtual environment.
5. Ensure **FFmpeg** is available in the chosen environment.
6. Summarise connection information for the user.

Idempotency is a core design goal.  Every function checks whether its work has already been completed and exits early when possible.

## Constants and Paths
At the top of the script several constants define network ports, model information and filesystem locations:
```python
OPENWEBUI_PORT = 3000
OLLAMA_PORT    = 11434
MODEL_REPO  = "ggml-org/SmolLM3-3B-GGUF"
MODEL_FILE  = "SmolLM3-Q4_K_M.gguf"  # ~1.9 GB — good for 4 GB VRAM
MODEL_NAME  = "smollm3-local"
BASE               = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "smollm3_stack"
DOWNLOADS_DIR      = BASE / "downloads"
OLLAMA_DIR         = BASE / "ollama"
OLLAMA_MODELS_DIR  = BASE / "models"
OPENWEBUI_DIR      = BASE / "openwebui"
OPENWEBUI_VENV     = BASE / "openwebui-venv"
LOGS_DIR           = BASE / "logs"
```
These can be modified to alter default behaviour such as ports or installation directories.

## Logging and Utilities
`setup_logging()` configures both console and file handlers and writes `latest-log.txt` for convenience.  The `run()` helper streams the output of subprocesses line by line into the logger, ensuring that every external command is captured.

`resumable_download()` handles HTTP downloads that may be interrupted.  It relies on `head_content_length()` and `_stream_copy()` to support range requests and progress logging.

## Component Installers
### Ollama
- `ensure_ollama_installed()` downloads the Windows zip release and extracts it into `OLLAMA_DIR`.  The path is appended to the user’s PATH environment variable.
- `ensure_ollama_running_and_autostart()` starts `ollama serve` in the background if it is not already running and registers a scheduled task so it starts on user logon.

### SmolLM3 Model
- `ensure_smollm3_model()` downloads the GGUF file, writes a `Modelfile` with tuning parameters and imports the model into Ollama under `MODEL_NAME` if it has not been created previously.

### Open WebUI
The installer chooses the runtime environment automatically:
1. **Docker** – `ensure_openwebui_docker()` pulls and runs the `ghcr.io/open-webui/open-webui:latest` image.  It exposes port `OPENWEBUI_PORT` and links to the local Ollama API.
2. **WSL** – `ensure_openwebui_wsl(distro=None)` installs Open WebUI into the given distribution (or the default when `distro` is `None`) and configures a scheduled task to start it.
3. **pip/venv** – `ensure_openwebui_pip()` creates a Windows virtual environment, installs Open WebUI and schedules it to start at logon.

### FFmpeg
`ensure_ffmpeg_on_host()` and `ensure_ffmpeg_in_container()` install FFmpeg via `winget` or the appropriate package manager.  When running in WSL the installer tries `apt`, `apk` or `dnf` as needed.

## Scheduling and Autostart
Two helper functions manage startup integration:
- `try_create_logon_task()` creates a Windows Scheduled Task using `schtasks.exe` when permissions allow.  It falls back to placing a `.cmd` shortcut in the Startup folder via `create_startup_cmd()` if task creation fails.
- The tasks used are "Ollama Serve" for the model server and "Open WebUI" (or "Open WebUI (WSL)") for the interface.

## Development Tips
- Use `python -m py_compile install-smollm3-openwebui-unattended.py` to perform a quick syntax check before committing.
- The script is intended to run on Windows; on other platforms it exits early.  You can comment out the platform guard during development on Linux but ensure it is restored before committing.
- All subprocess invocations should route through the `run()` helper to maintain consistent logging.
- When adding downloads prefer `resumable_download()` to provide HTTP range support and progress feedback.
- Any new scheduled task should use `try_create_logon_task()` to benefit from the fallback mechanism.

## Extending the Installer
- **Additional models**: replicate `ensure_smollm3_model()` for the new model, adjusting the `Modelfile` and `MODEL_NAME` as needed.
- **Different runtime environments**: new back‑ends (e.g., Podman) can hook into the Open WebUI decision tree in `main()`.
- **Configuration parameters**: expose new options through `argparse` and reference them within the relevant functions.

## Project Governance
Contributions are welcome.  Review `CONTRIBUTING.md` for coding standards and workflow, and `CODE_OF_CONDUCT.md` for community expectations.  Keep the changelog up to date when adding features or fixing bugs.

