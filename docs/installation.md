# Installation Guide

This guide walks through running the unattended installer on Windows 11.

1. **Install Python**: Ensure Python 3.8 or later is installed and available on your PATH.
2. **Download the script**: Obtain `install-smollm3-openwebui-unattended.py` from the repository.
3. **Open PowerShell** and navigate to the directory containing the script.
4. **Run the installer**:
   ```powershell
   python install-smollm3-openwebui-unattended.py
   ```
5. The script downloads Ollama, the SmolLM3-3B model, and sets up Open WebUI.
6. After completion, visit `http://localhost:3000` to access the web interface.

To uninstall the stack:
```powershell
python install-smollm3-openwebui-unattended.py --uninstall
```
This removes installed components and scheduled tasks.
