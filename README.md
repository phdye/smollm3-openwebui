# Tomex

An unattended installer for Windows 11 that sets up Ollama, the SmolLM3-3B model, Open WebUI, and FFmpeg in one step.

## Features
- Resumable, idempotent installation
- Fetches and configures SmolLM3-3B from the ggml-org repository
- Installs Open WebUI via Docker (preferred) or a Python virtual environment
- Ensures FFmpeg is present for audio features
- Logs every action for troubleshooting
- Optional WSL backend for Open WebUI via `--wsl <distro>`
- WSL backend installs Open WebUI inside its own Python virtual environment
- Provides start/stop scripts accessible from Windows and WSL

## Prerequisites
- Windows 11
- Python 3.9+
- Internet connection for downloading assets

## Usage
Run the installer from PowerShell or Command Prompt:

```powershell
python tomex-installer.py [--wsl <distro-name>]
```

Use `--wsl <distro-name>` to run Open WebUI inside the specified WSL distribution when Docker is unavailable.

The script can be re-run safely. It will skip steps that are already complete. Logs are written to `%LOCALAPPDATA%\tomex\logs`.

## Repository structure
- `tomex-installer.py` – main installer script
- `docs/` – additional documentation such as usage guides

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidance on how to propose changes.

## License
This project is released under the [MIT License](LICENSE).
