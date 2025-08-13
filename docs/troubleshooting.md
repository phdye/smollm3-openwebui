# Troubleshooting

Common issues and how to resolve them.

## Installation Hangs
Check the log file pointed to in `logs/latest-log.txt`. Slow network connections may require more time.

## Ports Already in Use
If ports 3000 or 11434 are occupied, stop the conflicting services or adjust the `OPENWEBUI_PORT` and `OLLAMA_PORT` constants in the script.

## Uninstall Fails
Ensure the script has permission to remove scheduled tasks and files. Running PowerShell as Administrator may help.

## 500: unable to load model
This error usually means the model was created in a different directory than the one `ollama serve` uses.
Remove the `smollm3_stack\\models` folder and run the installer again, or ensure `OLLAMA_MODELS` points to
`smollm3_stack\\models` when running `ollama create`.
