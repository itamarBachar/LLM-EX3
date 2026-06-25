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

install_shell_integration() {
    echo "🔧 Installing shell integration..."
    local doit_dir="$HOME/.doit"
    mkdir -p "$doit_dir"
    
    local integration_file="$doit_dir/shell_integration.sh"
    cat << 'EOF' > "$integration_file"
# DoIt Shell Navigation Integration (supports cd, pushd, popd, user awareness & multi-tasking)

if [ -n "$BASH_VERSION" ]; then
    # 1. Initialize session ID for Bash
    if [ -z "$DOIT_SESSION_ID" ]; then
        export DOIT_SESSION_ID="session_$(tty | tr -d '/')_$(date +%s)_$RANDOM"
    fi

    # 2. Setup prompt command hook for Bash
    doit_prompt_command() {
        # Temporarily clear HISTTIMEFORMAT to ensure consistent output format from history 1
        local old_timeformat="$HISTTIMEFORMAT"
        export HISTTIMEFORMAT=""
        local last_hist=$(history 1)
        export HISTTIMEFORMAT="$old_timeformat"

        # Extract command number and command text
        local cmd_num=$(echo "$last_hist" | awk '{print $1}')
        local last_cmd=$(echo "$last_hist" | sed 's/^[ ]*[0-9]*[ ]*//')

        if [ -n "$DOIT_SESSION_ID" ] && [ -n "$cmd_num" ] && [ -n "$last_cmd" ] && [ "$cmd_num" != "$DOIT_LAST_LOGGED_NUM" ]; then
            export DOIT_LAST_LOGGED_NUM="$cmd_num"
            # Filter out 'doit' invocations
            if [[ ! "$last_cmd" =~ ^[[:space:]]*doit ]]; then
                mkdir -p "$HOME/.doit/sessions"
                echo "$last_cmd" >> "$HOME/.doit/sessions/$DOIT_SESSION_ID.log"
            fi
        fi
    }

    # Register the prompt command safely
    if [[ "$PROMPT_COMMAND" != *doit_prompt_command* ]]; then
        PROMPT_COMMAND="doit_prompt_command${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
    fi
fi

doit() {
    # Flush history before execution so doit sees recent manual commands
    history -a
    # Create a temporary file to hold the navigation command
    local cd_file=$(mktemp)
    export DOIT_CD_FILE="$cd_file"
    
    # Run the real 'doit' executable
    command doit "$@"
    local exit_code=$?
    
    # If the python process wrote a navigation command, evaluate it
    if [ -f "$cd_file" ] && [ -s "$cd_file" ]; then
        local cmd=$(cat "$cd_file")
        # Prefix with a space and use ignorespace to avoid logging to bash history
        local old_histcontrol="$HISTCONTROL"
        export HISTCONTROL="ignorespace"
        eval " $cmd"
        export HISTCONTROL="$old_histcontrol"
    fi
    
    rm -f "$cd_file"
    unset DOIT_CD_FILE
    return $exit_code
}
EOF
    chmod +x "$integration_file"

    local integration_line="[ -f \"\$HOME/.doit/shell_integration.sh\" ] && source \"\$HOME/.doit/shell_integration.sh\""
    
    # Check ~/.bashrc
    if [ -f "$HOME/.bashrc" ]; then
        if ! grep -q "shell_integration.sh" "$HOME/.bashrc"; then
            echo "" >> "$HOME/.bashrc"
            echo "# Added by DoIt installation" >> "$HOME/.bashrc"
            echo "$integration_line" >> "$HOME/.bashrc"
            echo "✓ Added shell integration to ~/.bashrc"
        else
            echo "✓ Shell integration already configured in ~/.bashrc"
        fi
    fi
    
}

install_shell_integration

echo ""
echo "✅ Installation complete!"
echo ""
echo "📝 Required setup:"
echo "   1. API Key:"
echo "      - OpenAI: export OPENAI_API_KEY='your-openai-key'"
echo "      - Gemini: export GEMINI_API_KEY='your-gemini-key'"
echo "      (Add to ~/.bashrc to persist across sessions)"
echo "   2. Reload shell config to enable navigation (cd/pushd/popd) support:"
echo "      source ~/.bashrc"
echo ""
