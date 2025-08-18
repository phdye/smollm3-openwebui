# WSL Installer

The `installers/wsl.py` script sets up the complete Tomex stack inside a Windows Subsystem for Linux (WSL) distribution. It installs required software, creates convenience scripts, and immediately starts the services.

## High-Level Flow
1. **Argument parsing** – `install()` prepares a CLI parser (currently without options) and begins the installation sequence.
2. **Ollama** – `ensure_ollama()` checks for the `ollama` binary and runs the official installation script if it is missing.
3. **Model download** – `ensure_model()` pulls the SmolLM3 3B model using `ollama pull smollm3:3b`.
4. **FFmpeg** – `ensure_ffmpeg()` installs FFmpeg from `apt` when it is not already available.
5. **Open WebUI** – `ensure_openwebui()` installs or upgrades the `open-webui` Python package using `pip`.
6. **Helper scripts** – `create_scripts()` writes executable `start-tomex.sh` and `stop-tomex.sh` scripts in the user’s home directory to launch and terminate Ollama and Open WebUI.
7. **Launch stack** – `start_stack()` executes `start-tomex.sh`, starting both services immediately.

## Utility Function
- `_run(cmd)` prints each command it runs and raises an error if the command fails, ensuring the installer stops on errors.

## Generated Scripts
- **~/start-tomex.sh** – runs `ollama serve` and `open-webui --host 0.0.0.0` in the background.
- **~/stop-tomex.sh** – kills processes for Open WebUI and `ollama serve` using `pkill -f`.

## Usage
Run the installer inside a WSL distribution:

```bash
python installers/wsl.py
```

After completion, use the helper scripts to control the stack:

```bash
~/start-tomex.sh  # start services
~/stop-tomex.sh   # stop services
```
