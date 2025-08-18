# WSL Installer

The `installers/wsl.py` script sets up Open WebUI inside a Windows Subsystem for Linux (WSL) distribution while relying on an Ollama instance running on the Windows host for model execution. Keeping Ollama on Windows allows it to access the GPU directly.

## High-Level Flow
1. **Argument parsing** – `install()` prepares a CLI parser (currently without options) and begins the installation sequence.
2. **Detect host Ollama** – `ensure_host_ollama()` locates the Windows host and waits for the Ollama API to respond.
3. **FFmpeg** – `ensure_ffmpeg()` installs FFmpeg from `apt` when it is not already available.
4. **Open WebUI** – `ensure_openwebui()` installs or upgrades the `open-webui` Python package using `pip` for the dedicated `tomex` account.
5. **Helper scripts** – `create_scripts()` writes executable `start-tomex.sh` and `stop-tomex.sh` scripts in `/home/tomex` to launch and terminate Open WebUI. The scripts automatically point Open WebUI at the host’s Ollama service.
6. **Launch stack** – `start_stack()` executes `start-tomex.sh` as the `tomex` user, starting Open WebUI immediately.

## Utility Function
- `_run(cmd)` prints each command it runs and raises an error if the command fails, ensuring the installer stops on errors.

## Generated Scripts
- **/home/tomex/start-tomex.sh** – sets `OLLAMA_HOST` to the Windows IP and runs `open-webui --host 0.0.0.0` in the background.
- **/home/tomex/stop-tomex.sh** – kills the Open WebUI process using `pkill -f`.

## Usage
Run the installer inside a WSL distribution:

```bash
python installers/wsl.py
```

After completion, use the helper scripts to control the stack (run them as the `tomex` user):

```bash
sudo -u tomex /home/tomex/start-tomex.sh  # start services
sudo -u tomex /home/tomex/stop-tomex.sh   # stop services
```
