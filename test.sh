#!/bin/bash
# Test script to verify doit installation and functionality using uv

set -e

echo "🧪 DoIt Test Suite (with uv)"
echo "==========================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test 1: uv availability
echo "Test 1: Checking uv..."
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version)
    echo -e "${GREEN}✓ uv found: $UV_VERSION${NC}"
else
    echo -e "${RED}✗ uv not found. Please install uv first.${NC}"
    exit 1
fi

# Test 2: Python syntax
echo ""
echo "Test 2: Checking Python syntax..."
if uv run python3 -m py_compile "$SCRIPT_DIR/doit.py" "$SCRIPT_DIR/doit"/*.py 2>/dev/null; then
    echo -e "${GREEN}✓ All Python files have valid syntax${NC}"
else
    echo -e "${RED}✗ Syntax errors found${NC}"
    exit 1
fi

# Test 3: Module imports
echo ""
echo "Test 3: Checking module imports..."
IMPORT_RESULT=$(uv run python3 << 'PYEOF' 2>&1
try:
    from doit import main, response_parser, safety, command_executor
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
PYEOF
)

if [ "$IMPORT_RESULT" = "OK" ]; then
    echo -e "${GREEN}✓ All modules import successfully${NC}"
else
    echo -e "${RED}✗ Module import failed: $IMPORT_RESULT${NC}"
    exit 1
fi

# Test 4: Safety detection
echo ""
echo "Test 4: Testing safety detection..."
TEST_RESULT=$(uv run python3 << 'PYEOF'
import doit.safety as safety

safety.assess_command_risk_with_llm = lambda command: (
    True,
    "runs with elevated privileges",
) if command == "sudo reboot" else (False, "read-only")

checks = [
    safety.detect_filesystem_modification("rm -rf /")[0],
    safety.detect_filesystem_modification("mkdir demo")[0],
    safety.detect_filesystem_modification("mv old.txt new.txt")[0],
    safety.detect_dangerous_patterns("sudo reboot")[0],
    safety.detect_filesystem_modification('echo "a > b"')[0] is False,
    safety.should_execute_command("ls -la")[0],
]

print("PASS" if all(checks) else "FAIL")
PYEOF
)

if [ "$TEST_RESULT" = "PASS" ]; then
    echo -e "${GREEN}✓ Safety detection working${NC}"
else
    echo -e "${RED}✗ Safety detection failed${NC}"
    exit 1
fi

# Test 5: JSON parsing
echo ""
echo "Test 5: Testing JSON response parsing..."
PARSE_RESULT=$(uv run python3 << 'PYEOF'
from doit.response_parser import parse_llm_response
try:
    response = parse_llm_response('{"type":"command","command":"ls","explanation":"List"}')
    print("PASS" if response['type'] == 'command' else "FAIL")
except:
    print("FAIL")
PYEOF
)

if [ "$PARSE_RESULT" = "PASS" ]; then
    echo -e "${GREEN}✓ JSON parsing working${NC}"
else
    echo -e "${RED}✗ JSON parsing failed${NC}"
    exit 1
fi

# Test 6: Command execution
echo ""
echo "Test 6: Testing command execution..."
EXEC_RESULT=$(uv run python3 << 'PYEOF'
from doit.command_executor import run_shell_command
result = run_shell_command("echo 'test'")
print("PASS" if result['returncode'] == 0 and 'test' in result['stdout'] else "FAIL")
PYEOF
)

if [ "$EXEC_RESULT" = "PASS" ]; then
    echo -e "${GREEN}✓ Command execution working${NC}"
else
    echo -e "${RED}✗ Command execution failed${NC}"
    exit 1
fi

# Test 7: Executable permission
echo ""
echo "Test 7: Checking executable permissions..."
if [ -x "$SCRIPT_DIR/setup.sh" ] && [ -x "$SCRIPT_DIR/doit.py" ]; then
    echo -e "${GREEN}✓ Executables have correct permissions${NC}"
else
    echo -e "${YELLOW}⚠ Fixing executable permissions...${NC}"
    chmod +x "$SCRIPT_DIR/setup.sh" "$SCRIPT_DIR/doit.py"
    echo -e "${GREEN}✓ Permissions fixed${NC}"
fi

# Test 8: API key configuration based on active model
echo ""
echo "Test 8: Checking API key configuration..."
set +e
KEY_CHECK=$(uv run python3 << 'PYEOF' 2>&1
import os
import sys
from doit.config import get_config

try:
    config = get_config()
    provider = config.get_provider()
    model = config.get_model_name()
    
    if provider == "api":
        if "gemini" in model:
            key_name = "GEMINI_API_KEY"
        elif "claude" in model or "anthropic" in model:
            key_name = "ANTHROPIC_API_KEY"
        else:
            key_name = "OPENAI_API_KEY"
            
        if not os.environ.get(key_name):
            print(f"WARN: {key_name} is not set, which is required for model '{model}'")
            sys.exit(2)
        else:
            print(f"OK: {key_name} is configured successfully")
    else:
        print(f"OK: Local provider '{provider}' selected (no keys required)")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PYEOF
)
EXIT_CODE=$?
set -e
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ API configuration: $KEY_CHECK${NC}"
elif [ $EXIT_CODE -eq 2 ]; then
    echo -e "${YELLOW}⚠ API configuration: $KEY_CHECK${NC}"
else
    echo -e "${RED}✗ Config check failed: $KEY_CHECK${NC}"
    exit 1
fi

# Summary
echo ""
echo "================="
echo -e "${GREEN}✅ All tests passed!${NC}"
echo "================="
echo ""
echo "Next steps:"
echo "1. Run setup: ./setup.sh"
echo "2. Set your API key if needed (e.g. export GEMINI_API_KEY='your-key')"
echo "3. Try: doit \"list files in my home directory\""
echo ""
