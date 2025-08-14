# Usage Guide

This guide provides step-by-step instructions for running the unattended installer.

## 1. Install Python
Ensure [Python 3.9 or later](https://www.python.org/downloads/) is installed and available in your PATH.

## 2. Download the script
Clone the repository or download the latest ZIP archive from the releases page. Save the script in a convenient directory.

## 3. Run from PowerShell
Open PowerShell and navigate to the directory containing the script:

```powershell
cd path\to\script
python install-smollm3-openwebui-unattended.py
```

The script will download and configure Ollama, the SmolLM3-3B model, Open WebUI, and FFmpeg. It may take several minutes depending on network speed.

## 4. Access the services
- Open WebUI will be available at `http://localhost:3000`
- The Ollama API will run at `http://localhost:11434`

## 5. Logs
Detailed logs are written to `%LOCALAPPDATA%\smollm3_stack\logs`. Each run creates a timestamped log file and updates `latest-log.txt` with the most recent path.

## 6. Re-running
You can re-run the script at any time. It detects completed steps and skips them, making the process idempotent.
