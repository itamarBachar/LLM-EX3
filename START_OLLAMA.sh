#!/bin/bash
# Start the local Ollama server for DoIt.

set -e

if ! command -v ollama &> /dev/null; then
    echo "✗ Ollama is not installed or not on PATH."
    echo "  Run ./SETUP_MODELS.sh --install-ollama first."
    exit 1
fi

if pgrep -x ollama >/dev/null 2>&1; then
    echo "✓ Ollama server already appears to be running."
    echo "  Test it with: ollama list"
    exit 0
fi

echo "Starting Ollama server on http://127.0.0.1:11434"
echo "Keep this terminal open while using local models with doit."

exec ollama serve