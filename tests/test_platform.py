import subprocess
import sys
from pathlib import Path


def test_non_windows_invocation():
    script = Path(__file__).resolve().parent.parent / "install-smollm3-openwebui-unattended.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "This script is intended for Windows 11." in result.stdout
