#!/bin/bash
# Setup script for installing doit to system PATH using uv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_BIN="/usr/local/bin/doit"

echo "🚀 Installing doit CLI with uv..."

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed."
    echo "Please install uv: https://astral.sh/uv"
    echo "You can install it using: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ uv found: $(uv --version)"

# Install dependencies using uv sync
echo "📦 Syncing project dependencies with uv..."
uv sync --project "$SCRIPT_DIR"

# Install to /usr/local/bin or ~/.local/bin
install_wrapper() {
    local target="$1"
    echo "Installing wrapper script to $target..."
    cat << EOF > "$target"
#!/bin/bash
exec uv run --project "$SCRIPT_DIR" doit "\$@"
EOF
    chmod +x "$target"
}

if [ -w /usr/local/bin ]; then
    install_wrapper "$TARGET_BIN"
    echo "✓ Installed to $TARGET_BIN"
else
    echo "⚠️  /usr/local/bin is not writable. Installing to user bin directory..."
    
    USER_BIN="$HOME/.local/bin"
    mkdir -p "$USER_BIN"
    install_wrapper "$USER_BIN/doit"
    
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
echo "   1. Configuration: Copy doit.cfg to ~/doit.cfg (if not already done)"
echo "      cp \"$SCRIPT_DIR/doit.cfg\" ~/doit.cfg"
echo "   2. API Key:"
echo "      - OpenAI: export OPENAI_API_KEY='your-openai-key'"
echo "      - Gemini: export GEMINI_API_KEY='your-gemini-key'"
echo "      (Add to ~/.bashrc or ~/.zshrc to persist across sessions)"
echo ""
