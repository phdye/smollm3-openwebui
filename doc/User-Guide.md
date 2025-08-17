# User Guide

## Overview
The SmolLM3 Open WebUI stack provides an unattended way to set up a local chat environment on Windows 11.  A single Python script downloads and configures four major components:

1. **Ollama** – the lightweight model runner.
2. **SmolLM3‑3B model** – supplied as a pre‑quantised GGUF file.
3. **Open WebUI** – a browser based interface to interact with models via Ollama.
4. **FFmpeg** – optional but required for audio features such as speech‑to‑text.

The script can be re‑run safely.  It detects completed work and skips steps that are already done.  Logging captures every action making the process transparent and easy to troubleshoot.

## Requirements
- Windows 11 x64
- Python 3.9 or later available on the PATH
- Administrative rights are **not** required; the installer operates entirely in the user profile
- Internet connectivity for downloading assets
- Sufficient disk space (~8 GB to accommodate downloads and extracted files)

## Getting the Installer
1. Clone this repository or download the ZIP from the releases page.
2. Extract the contents and locate `install-smollm3-openwebui-unattended.py`.

For ease of use place the script in a directory without spaces in the path.

## Running the Installer
1. Open **PowerShell** or **Command Prompt**.
2. Change to the directory containing the script:
   ```powershell
   cd path\to\script
   ```
3. Execute the installer:
   ```powershell
   python install-smollm3-openwebui-unattended.py [--wsl [<distro-name>]]
   ```

### Command‑line Options
- `--wsl [<distro-name>]` – runs Open WebUI inside the default WSL distribution or the one specified.  This is useful when Docker is not available.  Specify a distribution name returned by `wsl -l` when targeting a non-default distro.

### What Happens During Installation
1. **Directory preparation** – all files live under `%LOCALAPPDATA%\smollm3_stack`.
2. **Ollama** – downloaded, extracted, added to the user PATH and started as a background service.  A scheduled task is registered so Ollama launches automatically at logon.
3. **SmolLM3‑3B model** – the GGUF model and an accompanying Modelfile are stored in `%LOCALAPPDATA%\smollm3_stack\models`.  The model is imported into Ollama as `smollm3-local` with context and GPU parameters tuned for local use.
4. **Open WebUI** – preference order:
   - Docker container named `open-webui`.
   - WSL virtual environment (when `--wsl` is supplied, optionally with a distribution name).
   - Python virtual environment in `%LOCALAPPDATA%\smollm3_stack\openwebui-venv`.
   Autostart is configured through a scheduled task so the interface is available after each login, and the services are started immediately after installation.
5. **FFmpeg** – installed inside the Docker container, inside WSL, or on the host depending on how Open WebUI is executed.
6. **Logging** – every action and the output of invoked commands are written to `%LOCALAPPDATA%\smollm3_stack\logs`.  `latest-log.txt` points to the most recent log file.

### Idempotency and Resuming
The installer can be run repeatedly.  Downloads use HTTP range requests and are resumed if interrupted.  Existing installations of Ollama, models, or Open WebUI are detected and skipped, dramatically reducing subsequent execution time.

## Using the Stack
- **Open WebUI**: visit `http://localhost:3000` in a browser.  The interface exposes chat history, model selection and settings.  The SmolLM3 model appears as `smollm3-local`.
- **Ollama API**: available at `http://localhost:11434`.  Advanced users can interact with it programmatically using HTTP requests.
- **Audio features**: once FFmpeg is present the interface allows speech‑to‑text and text‑to‑speech features.

### Starting and Stopping
- The scheduled tasks created by the installer automatically start Ollama and Open WebUI at user login.
- To start or stop them manually use the Windows **Task Scheduler** or run/stop the `open-webui` Docker container (or WSL/venv process).
- If you prefer a simpler startup mechanism the installer writes a fallback `Open WebUI.cmd` file into the Startup folder when task creation fails.

### Managing Models
- The imported SmolLM3 model resides in `%LOCALAPPDATA%\smollm3_stack\models`.
- Additional models can be added using standard Ollama commands, for example:
  ```powershell
  ollama pull llama3
  ollama run llama3
  ```
- To remove the SmolLM3 model run `ollama rm smollm3-local`.

### Updating Components
Re‑run the installer at any time to pull the latest versions of Ollama, Open WebUI and the model.  The script recognises existing files and only downloads newer versions.

## Troubleshooting
- **Check the logs**: open `%LOCALAPPDATA%\smollm3_stack\logs\latest-log.txt` to find the full log path for the most recent run.
- **Ports already in use**: ensure nothing else is bound to ports 3000 (Open WebUI) or 11434 (Ollama).
- **No Docker installed**: install Docker Desktop or run the installer with `--wsl [<distro>]` or without Docker to use the Python virtual environment.
- **Model download interrupted**: simply re-run the installer; the download resumes where it left off.

## Uninstalling
1. Stop the `open-webui` container or process and stop the Ollama service.
2. Delete `%LOCALAPPDATA%\smollm3_stack`.
3. Remove scheduled tasks "Ollama Serve" and "Open WebUI" via Task Scheduler.
4. Optionally remove the `ollama` and `open-webui` entries from your PATH and uninstall Docker/WSL if no longer needed.

## Frequently Asked Questions
**Q: Can I change the ports?**  Yes, edit the constants `OPENWEBUI_PORT` and `OLLAMA_PORT` at the top of the script and rerun the installer.

**Q: Is administrative access required?**  No.  All components install into the user profile and scheduled tasks run in the user context.

**Q: Can I run the installer offline?**  No.  Internet connectivity is required for the initial downloads.

**Q: How do I add my own model?**  Use `ollama pull` or `ollama create` with your Modelfile.  Open WebUI will automatically expose any model that Ollama can serve.

