#!/bin/bash
# Multi-Model Setup and Usage Guide using uv

echo "=== DoIt Multi-Model Configuration Guide ==="
echo ""

# Check if config is loadable using our python config library
echo "=== Current Configuration ==="
if ! uv run python3 -c 'from doit.config import get_config; get_config()' &>/dev/null; then
    echo "✗ Configuration file NOT found or invalid."
    echo "  Please copy the template config: cp doit.cfg ~/doit.cfg"
    exit 1
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

echo ""
echo "=== Available Model Providers ==="
echo ""
echo "1. API Provider (provider = api)"
echo "   Models: gpt-4o-mini, gemini/gemini-1.5-flash, anthropic/claude-3-5-sonnet-20240620, mixtral-8x7b-32768"
echo "   Setup: Set API keys in environment (OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, etc.)"
echo "   Edit ~/doit.cfg (or ~/.doit.cfg):"
echo "     [model]"
echo "     provider = api"
echo "     api_model = gemini-1.5-flash"
echo ""

echo "2. Local Model without Tool-Calling (provider = local_no_tools)"
echo "   Models: mistral, llama2, neural-chat"
echo "   Setup: Install ollama (ollama.ai), run: ollama pull mistral"
echo "   Edit ~/doit.cfg:"
echo "     [model]"
echo "     provider = local_no_tools"
echo "     local_model_no_tools = mistral"
echo ""

echo "3. Local Model with Tool-Calling (provider = local_with_tools)"
echo "   Models: neural-chat, llama2-tool-calling"
echo "   Setup: Install ollama, run: ollama pull neural-chat"
echo "   Edit ~/doit.cfg:"
echo "     [model]"
echo "     provider = local_with_tools"
echo "     local_model_with_tools = neural-chat"
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
