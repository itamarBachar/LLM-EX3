#!/bin/bash
# Test script to verify doit installation and functionality

set -e

echo "🧪 DoIt Test Suite"
echo "================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Test 1: Python availability
echo "Test 1: Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ Python found: $PYTHON_VERSION${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi

# Test 2: Python syntax
echo ""
echo "Test 2: Checking Python syntax..."
if python3 -m py_compile "$SCRIPT_DIR/doit.py" "$SCRIPT_DIR/doit"/*.py 2>/dev/null; then
    echo -e "${GREEN}✓ All Python files have valid syntax${NC}"
else
    echo -e "${RED}✗ Syntax errors found${NC}"
    exit 1
fi

# Test 3: Module imports
echo ""
echo "Test 3: Checking module imports..."
python3 << 'PYEOF' > /dev/null 2>&1
try:
    from doit import response_parser, safety, command_executor
    print("OK")
except Exception as e:
    print(f"FAILED: {e}")
    exit(1)
PYEOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All modules import successfully${NC}"
else
    echo -e "${RED}✗ Module import failed${NC}"
    exit 1
fi

# Test 4: Safety detection
echo ""
echo "Test 4: Testing safety detection..."
TEST_RESULT=$(python3 << 'PYEOF'
from doit.safety import detect_dangerous_patterns
is_dangerous, reason = detect_dangerous_patterns("rm -rf /")
print("PASS" if is_dangerous else "FAIL")
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
PARSE_RESULT=$(python3 << 'PYEOF'
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
EXEC_RESULT=$(python3 << 'PYEOF'
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
if [ -x "$SCRIPT_DIR/doit" ] && [ -x "$SCRIPT_DIR/setup.sh" ]; then
    echo -e "${GREEN}✓ Executables have correct permissions${NC}"
else
    echo -e "${YELLOW}⚠ Fixing executable permissions...${NC}"
    chmod +x "$SCRIPT_DIR/doit" "$SCRIPT_DIR/setup.sh"
    echo -e "${GREEN}✓ Permissions fixed${NC}"
fi

# Test 8: API key configuration
echo ""
echo "Test 8: Checking OpenAI API key..."
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠ OPENAI_API_KEY not set${NC}"
    echo "   Set with: export OPENAI_API_KEY='sk-...'"
else
    echo -e "${GREEN}✓ OPENAI_API_KEY is set${NC}"
fi

# Summary
echo ""
echo "================="
echo -e "${GREEN}✅ All tests passed!${NC}"
echo "================="
echo ""
echo "Next steps:"
echo "1. Set your API key: export OPENAI_API_KEY='sk-...'"
echo "2. Try: doit \"list files in my home directory\""
echo "3. Read: QUICKSTART.md and README.md"
echo ""
