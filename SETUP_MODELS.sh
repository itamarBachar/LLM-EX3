#!/bin/bash
# Multi-Model Setup and Usage Guide

echo "=== DoIt Multi-Model Configuration Guide ==="
echo ""

# Step 1: Verify config file exists
if [ -f ~/.doit.cfg ]; then
    echo "✓ Configuration file found at ~/.doit.cfg"
else
    echo "✗ Configuration file NOT found"
    echo "  Run: cp doit.cfg ~/"
    exit 1
fi

echo ""
echo "=== Current Configuration ==="
python3 << 'EOF'
from doit.config import get_config
config = get_config()
print(f"Provider:        {config.get_provider()}")
print(f"Model:           {config.get_model_name()}")
print(f"Temperature:     {config.get_temperature()}")
print(f"Max Tokens:      {config.get_max_tokens()}")
print(f"Max Retries:     {config.get_max_retries()}")
print(f"Tool Support:    {'Yes' if config.has_tool_calling_support() else 'No'}")
EOF

echo ""
echo "=== Available Model Providers ==="
echo ""
echo "1. API Provider (provider = api)"
echo "   Models: gpt-4o-mini, gpt-4-turbo, claude-3-sonnet, mixtral-8x7b-32768"
echo "   Setup: Set API keys in environment (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)"
echo "   Edit ~/.doit.cfg:"
echo "     [model]"
echo "     provider = api"
echo "     api_model = gpt-4o-mini"
echo ""

echo "2. Local Model without Tool-Calling (provider = local_no_tools)"
echo "   Models: mistral, llama2, neural-chat"
echo "   Setup: Install ollama (ollama.ai), run: ollama pull mistral"
echo "   Edit ~/.doit.cfg:"
echo "     [model]"
echo "     provider = local_no_tools"
echo "     local_model_no_tools = mistral"
echo ""

echo "3. Local Model with Tool-Calling (provider = local_with_tools)"
echo "   Models: neural-chat, llama2-tool-calling"
echo "   Setup: Install ollama, run: ollama pull neural-chat"
echo "   Edit ~/.doit.cfg:"
echo "     [model]"
echo "     provider = local_with_tools"
echo "     local_model_with_tools = neural-chat"
echo ""

echo "=== Switching Models ==="
echo ""
echo "To switch to a different model:"
echo "1. Edit ~/.doit.cfg"
echo "2. Change 'provider' setting"
echo "3. Update the corresponding model name"
echo "4. Restart your application"
echo ""

echo "Example: Switch to Anthropic Claude"
echo "  [model]"
echo "  provider = api"
echo "  api_model = anthropic/claude-3-sonnet-20240229"
echo ""
echo "Then set: export ANTHROPIC_API_KEY=your_key_here"
