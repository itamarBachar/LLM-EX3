#!/bin/bash
# Multi-Model Setup and Usage Guide using uv

DOWNLOAD_REQUESTED=false
INSTALL_OLLAMA_REQUESTED=false

if [[ "$1" == "--download" ]]; then
    DOWNLOAD_REQUESTED=true
elif [[ "$1" == "--install-ollama" ]]; then
    INSTALL_OLLAMA_REQUESTED=true
fi

install_ollama() {
    if command -v ollama &> /dev/null; then
        echo "✓ Ollama is already installed: $(command -v ollama)"
        return 0
    fi

    if ! command -v curl &> /dev/null; then
        echo "✗ curl is required to install Ollama."
        return 1
    fi

    echo ""
    echo "=== Installing Ollama ==="
    echo "This uses the official installer from https://ollama.com/install.sh"
    echo "You may be prompted for sudo access."
    echo ""

    curl -fsSL https://ollama.com/install.sh | sh
}

download_configured_model() {
    local config_output
    local provider
    local model
    local ollama_model

    config_output=$(uv run python3 << 'EOF'
from doit.config import get_config

config = get_config()
print(config.get_provider())
print(config.get_model_name())
EOF
)

    provider=$(printf '%s\n' "$config_output" | sed -n '1p')
    model=$(printf '%s\n' "$config_output" | sed -n '2p')

    if [[ "$provider" == "api" ]]; then
        echo "✗ Current provider is 'api'. There is no local model to download."
        echo "  Switch provider in ~/doit.cfg to local_no_tools or local_with_tools first."
        return 1
    fi

    if [[ "$model" != ollama/* ]]; then
        echo "✗ Automatic download only supports Ollama models right now."
        echo "  Configured model: $model"
        echo "  Use your serving stack's own download flow for non-Ollama models."
        return 1
    fi

    if ! command -v ollama &> /dev/null; then
        echo "✗ Ollama is not installed or not on PATH."
        echo "  Install it from https://ollama.ai and retry."
        return 1
    fi

    ollama_model="${model#ollama/}"

    echo ""
    echo "=== Downloading Configured Local Model ==="
    echo "Provider: $provider"
    echo "Model:    $ollama_model"
    echo ""

    ollama pull "$ollama_model"
}

echo "=== DoIt Multi-Model Configuration Guide ==="
echo ""

# Check if config is loadable using our python config library
echo "=== Current Configuration ==="
if ! uv run python3 -c 'from doit.config import get_config; get_config()' &>/dev/null; then
    echo "✗ Configuration file NOT found or invalid."
    echo "  Please copy the template config: cp doit.cfg ~/doit.cfg"
    exit 1
fi

if [[ "$INSTALL_OLLAMA_REQUESTED" == true ]]; then
    install_ollama
    exit $?
fi

uv run python3 << 'EOF'
from doit.config import get_config
try:
    config = get_config()
    print(f"Config File:     {config.config_path}")
    print(f"Provider:        {config.get_provider()}")
    print(f"Model:           {config.get_model_name()}")
    print(f"Temperature:     {config.get_temperature()}")
    print(f"Max Tokens:      {config.get_max_tokens()}")
    print(f"Max Retries:     {config.get_max_retries()}")
    print(f"Tool Support:    {'Yes' if config.has_tool_calling_support() else 'No'}")
except Exception as e:
    print(f"Error loading configuration: {e}")
EOF

if [[ "$DOWNLOAD_REQUESTED" == true ]]; then
    download_configured_model
    exit $?
fi

echo ""
echo "=== Available Model Providers ==="
echo ""
echo "1. API Provider (provider = api)"
echo "   Models: openai/gpt-4o-mini, gemini/gemini-1.5-flash, anthropic/claude-3-5-sonnet-20240620, groq/mixtral-8x7b-32768"
echo "   Setup: Set API keys in environment (OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, etc.)"
echo "   Edit ~/doit.cfg (or ~/.doit.cfg):"
echo "     [model]"
echo "     provider = api"
echo "     api_model = openai/gpt-4o-mini"
echo ""

echo "2. Local Model without Tool-Calling (provider = local_no_tools)"
echo "   Models: ollama/gemma3:4b, ollama/llama3:8b"
echo "   Setup: Install ollama (ollama.ai), run: ollama pull gemma3:4b"
echo "   Edit ~/doit.cfg:"
echo "     [model]"
echo "     provider = local_no_tools"
echo "     local_model_no_tools = ollama/gemma3:4b"
echo ""

echo "3. Local Model with Tool-Calling (provider = local_with_tools)"
echo "   Models: ollama/qwen3:4b-instruct, ollama/mistral:7b"
echo "   Setup: Install ollama, run: ollama pull qwen3:4b-instruct"
echo "   Edit ~/doit.cfg:"
echo "     [model]"
echo "     provider = local_with_tools"
echo "     local_model_with_tools = ollama/qwen3:4b-instruct"
echo ""

echo "=== Switching Models ==="
echo ""
echo "To switch to a different model:"
echo "1. Edit your doit.cfg"
echo "2. Change 'provider' setting"
echo "3. Update the corresponding model name"
echo "4. Run doit again"
echo ""
echo "Example: Switch to Gemini 1.5 Flash"
echo "  [model]"
echo "  provider = api"
echo "  api_model = gemini-1.5-flash"
echo ""
echo "Then set: export GEMINI_API_KEY=your_key_here"
echo ""
echo "To install Ollama automatically, run: ./SETUP_MODELS.sh --install-ollama"
echo "To download the configured Ollama model automatically, run: ./SETUP_MODELS.sh --download"
echo "To start the local Ollama server, run: ./START_OLLAMA.sh"
echo ""
