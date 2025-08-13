# SmolLM3 Open-WebUI Installer

An idempotent, restartable Python script that automates installing a local AI stack on Windows 11.
The installer provisions [Ollama](https://ollama.com/), downloads the SmolLM3-3B model,
and configures [Open WebUI](https://github.com/open-webui/open-webui) for easy web-based interaction.

## Features
- Resumable downloads and skip logic for already completed steps.
- Detailed logging of all operations with pointers to the latest log.
- Automatic creation of scheduled tasks or Startup-folder shortcuts.
- Uninstall routine that removes installed components and shortcuts.

## Requirements
- Windows 11
- Python 3.8+
- Internet access to download required components

## Quick Start
```bash
python install-smollm3-openwebui-unattended.py
```
The script checks if each component already exists and only performs missing steps.
For uninstalling, run:
```bash
python install-smollm3-openwebui-unattended.py --uninstall
```

## Documentation
Additional guides are available in the [docs](docs/installation.md) directory:
- [Installation guide](docs/installation.md)
- [Troubleshooting](docs/troubleshooting.md)

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on reporting issues and submitting patches.

## License
Distributed under the [MIT License](LICENSE).
