#!/bin/bash
# Setup script for installing doit to system PATH

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOIT_EXECUTABLE="$SCRIPT_DIR/doit_executable"
TARGET_BIN="/usr/local/bin/doit"

echo "🚀 Installing doit CLI..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -q -r "$SCRIPT_DIR/requirements.txt" || {
    echo "⚠️  Warning: Could not install dependencies with pip."
    echo "You may need to run: pip install -r requirements.txt"
}

# Make doit executable
chmod +x "$DOIT_EXECUTABLE"
echo "✓ Made doit executable"

# Install to /usr/local/bin (may require sudo)
if [ -w /usr/local/bin ]; then
    cat "$DOIT_EXECUTABLE" > "$TARGET_BIN"
    chmod +x "$TARGET_BIN"
    echo "✓ Installed to $TARGET_BIN"
else
    echo "⚠️  /usr/local/bin is not writable. Installing to user bin directory..."
    
    USER_BIN="$HOME/.local/bin"
    mkdir -p "$USER_BIN"
    cat "$DOIT_EXECUTABLE" > "$USER_BIN/doit"
    chmod +x "$USER_BIN/doit"
    
    # Check if user bin is in PATH
    if [[ ":$PATH:" == *":$USER_BIN:"* ]]; then
        echo "✓ Installed to $USER_BIN"
    else
        echo "⚠️  Warning: $USER_BIN is not in your PATH."
        echo "Add this line to your ~/.bashrc or ~/.bash_profile:"
        echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📝 Required setup:"
echo "   1. Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'"
echo "      (Add this to ~/.bashrc to persist across sessions)"
echo ""
echo "🎯 Try it out:"
echo "   doit \"list the files in my home directory\""
echo ""
