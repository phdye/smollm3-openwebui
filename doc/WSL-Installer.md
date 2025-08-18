# WSL Installer

The `installers/wsl.py` script sets up the complete Tomex stack inside a Windows Subsystem for Linux (WSL) distribution. It installs required software, creates convenience scripts, and immediately starts the services.

## High-Level Flow
1. **Argument parsing** – `install()` prepares a CLI parser (currently without options) and begins the installation sequence.
2. **Dedicated user** – `ensure_tomex_user()` creates a system account `tomex` with the home directory `/opt/tomex`.
3. **Ollama** – `ensure_ollama()` checks for the `ollama` binary and runs the official installation script if it is missing.
4. **Model download** – `ensure_model()` pulls the SmolLM3 3B model using `ollama pull smollm3:3b`.
5. **FFmpeg** – `ensure_ffmpeg()` installs FFmpeg from `apt` when it is not already available.
6. **Open WebUI** – `ensure_openwebui()` installs or upgrades the `open-webui` Python package for the `tomex` user.
7. **Helper scripts** – `create_scripts()` writes executable `start-tomex.sh` and `stop-tomex.sh` scripts in `/opt/tomex` owned by the `tomex` user to launch and terminate Ollama and Open WebUI.
8. **Launch stack** – `start_stack()` runs `start-tomex.sh` as the `tomex` user, starting both services immediately.

## Utility Function
- `_run(cmd)` prints each command it runs and raises an error if the command fails, ensuring the installer stops on errors.

## Generated Scripts
- **/opt/tomex/start-tomex.sh** – runs `ollama serve` and `open-webui --host 0.0.0.0` in the background.
- **/opt/tomex/stop-tomex.sh** – kills processes for Open WebUI and `ollama serve` using `pkill -f`.

## Usage
Run the installer inside a WSL distribution (with sufficient privileges to create system users and install packages):

```bash
python installers/wsl.py
```

After completion, use the helper scripts to control the stack:

```bash
/opt/tomex/start-tomex.sh  # start services
/opt/tomex/stop-tomex.sh   # stop services
```
