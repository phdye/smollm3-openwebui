# SmolLM3 Open WebUI Stack

An unattended installer for Windows 11 that sets up Ollama, the SmolLM3-3B model, Open WebUI, and FFmpeg in one step.

## Features
- Resumable, idempotent installation
- Fetches and configures SmolLM3-3B from the ggml-org repository
- Installs Open WebUI via Docker (preferred) or a Python virtual environment
- Ensures FFmpeg is present for audio features
- Logs every action for troubleshooting
- Creates Start Menu shortcuts for managing services and opening UIs

## Prerequisites
- Windows 11
- Python 3.9+
- Internet connection for downloading assets

## Usage
Run the installer from PowerShell or Command Prompt:

```powershell
python install-smollm3-openwebui-unattended.py
```

The script can be re-run safely. It will skip steps that are already complete. Logs are written to `%LOCALAPPDATA%\smollm3_stack\logs`.

## Repository structure
- `install-smollm3-openwebui-unattended.py` – main installer script
- `docs/` – additional documentation such as usage guides

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidance on how to propose changes.

## License
This project is released under the [MIT License](LICENSE).
