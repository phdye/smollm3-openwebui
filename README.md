# Tomex

An unattended installer for Windows 11 that sets up Ollama, the SmolLM3-3B model, Open WebUI, and FFmpeg in one step.

## Features
- Resumable, idempotent installation
- Fetches and configures SmolLM3-3B from the ggml-org repository
- Installs Ollama and Open WebUI together on the chosen backend (Docker, WSL, or a Python virtual environment)
- Ensures FFmpeg is present for audio features
- Logs every action for troubleshooting
- Optional WSL backend via `--backend wsl --distro <name>` installs the stack inside a specified distribution
- Provides start/stop scripts accessible from Windows and WSL

## Prerequisites
- Windows 11
- Python 3.9+
- Internet connection for downloading assets

## Usage
Run the wrapper from PowerShell or Command Prompt:

```powershell
python tomex-installer.py --backend <windows|wsl|docker|pip> [options]
```

The `--backend` flag selects which installer backend to run. On Windows it defaults to `windows`. Any remaining arguments are passed through to the
chosen backend. For example:

- `--backend wsl --distro <name>` installs Open WebUI inside the specified WSL distribution.
- `--backend docker` runs Open WebUI in a Docker container.
- `--backend pip` uses a local Python virtual environment.

The script can be re-run safely. It will skip steps that are already complete. Logs are written to `%LOCALAPPDATA%\tomex\logs`.

## Repository structure
- `tomex-installer.py` – wrapper that selects a backend installer
- `installers/` – individual backend installers (e.g., `windows.py`)
- `doc/` – additional documentation such as usage guides

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidance on how to propose changes.

## License
This project is released under the [MIT License](LICENSE).
