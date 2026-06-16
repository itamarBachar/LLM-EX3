# DoIt - Natural Language CLI Command Executor

DoIt is a powerful command-line tool that converts your natural language instructions into executable shell commands. Describe what you want in plain English, and let DoIt handle the rest.

The tool now supports multiple LLM providers, including API-based services (like OpenAI, Anthropic, and Groq) and local, offline models (like Gemma, Qwen, Llama, or Mistral via Ollama).

```bash
doit "list all files in my Documents folder larger than 10MB"
```

## ✨ Features

-   **Multi-Model Support**: Switch between different LLM providers and models with a simple configuration change.
-   **API & Local Models**: Supports both cloud-based APIs and local, offline models for privacy and flexibility.
-   **Natural Language Processing**: Describe what you want in plain English.
-   **Safety Checks**: Detects potentially dangerous commands (e.g., `rm -rf`, `chmod 777`) and requires confirmation before execution.
-   **Structured Output**: Get results with `stdout`, `stderr`, and exit codes.
-   **Timeout Protection**: Commands have a 20-second execution limit to prevent hangs.
-   **Error Handling**: Gracefully handles API failures and malformed responses.
-   **Modular Design**: Clean separation of concerns (LLM, parsing, execution, safety).

## 🚀 Quick Start

### 1. Prerequisites

-   Python 3.8+
-   A shell environment (like bash on Linux, macOS, or WSL)
-   An API key for an LLM provider (e.g., OpenAI) OR a local model server like Ollama.

### 2. Installation

Run the setup script to install dependencies and make the `doit` command available system-wide.

```bash
# Navigate to the project directory
cd /path/to/LLM-EX3

# Make the setup script executable and run it
chmod +x setup.sh
./setup.sh
```

This script will:
1.  ✅ Check for `uv` installation.
2.  ✅ Sync dependencies from `pyproject.toml` (including `litellm` and `python-dotenv`).
3.  ✅ Install a dynamic `doit` command wrapper to `/usr/local/bin` or `~/.local/bin` for easy global access.

### 3. Configuration

The `doit` tool is configured using a file named `doit.cfg` (or `.doit.cfg`) in your home directory, current directory, or project root directory.

```bash
# Copy the example configuration file to your home directory
cp doit.cfg ~/doit.cfg
```

Now, you can choose which model to use by editing `~/doit.cfg`.

#### Option A: Use an API Provider (Default)

This is the default configuration. All you need is an API key.

1.  **Set your API key**:
    *   **OpenAI**:
        ```bash
        export OPENAI_API_KEY="sk-..."
        ```
    *   **Gemini**:
        ```bash
        export GEMINI_API_KEY="your-gemini-key"
        ```
    To make it permanent, add this line to your `~/.bashrc` or `~/.zshrc` file.

2.  **Verify your configuration** in `~/doit.cfg`:
    ```ini
    [model]
    provider = api
    api_model = gpt-4o-mini  # Or gemini-1.5-flash
    ```

#### Option B: Use a Local Model (Offline & Private)

1.  **Install Ollama** by following the instructions at [ollama.ai](https://ollama.ai).

2.  **Download a local instruction model**:
    ```bash
    ollama pull gemma3:4b
    ```

3.  **Edit `~/doit.cfg`** to use the local model:
    ```ini
    [model]
    provider = local_no_tools
    local_model_no_tools = ollama/gemma3:4b
    ```

4.  **Or use a local model with tool-calling support**:
    ```ini
    [model]
    provider = local_with_tools
    local_model_with_tools = ollama/qwen3:4b-instruct
    ```

5.  **Download the configured Ollama model automatically**:
    ```bash
    ./SETUP_MODELS.sh --download
    ```
    This reads your current `~/doit.cfg` and runs `ollama pull` for the selected local model.

6.  **Install and start Ollama from the repo helpers**:
    ```bash
    ./SETUP_MODELS.sh --install-ollama
    ./START_OLLAMA.sh
    ```
    Use the first command if `ollama` is not installed yet. Use the second command to start the local server before running `doit` with local models.

## 💡 Usage

### Basic Commands

Simply pass your instruction as a string to the `doit` command.

```bash
# List files
doit "list all files in my home directory"

# Get system information
doit "show me the disk space usage"

# Create backups
doit "create a tar backup of my Documents folder"

# Use pipes for complex commands
doit "find all python files in the current directory and count them"
```

### Options

```bash
doit --help              # Show the help message
doit --version           # Show version information
doit -v "your command"   # Use verbose mode to see API responses and other details
```

## 🔧 Advanced Configuration

You can fine-tune the model's behavior by editing `~/doit.cfg`.

### Switching Models

You can easily switch between any provider supported by LiteLLM.

**Example: Switch to Anthropic's Claude Sonnet**

1.  **Set the API key**:
    ```bash
    export ANTHROPIC_API_KEY="your-api-key"
    ```

2.  **Update `~/doit.cfg`**:
    ```ini
    [model]
    provider = api
    api_model = anthropic/claude-3-5-sonnet-20240620
    ```

### Available Configuration Settings

Here are all the settings available in `~/doit.cfg`:

```ini
[model]
# Which provider to use: api, local_no_tools, local_with_tools
provider = api

# --- Model Names ---
# For API provider (format: provider/model or just model for OpenAI)
api_model = gpt-4o-mini

# For local models without tool-calling support
local_model_no_tools = ollama/gemma3:4b

# For local models with tool-calling support
local_model_with_tools = ollama/qwen3:4b-instruct

# --- Behavior ---
# Model temperature (0=deterministic, 1=creative)
temperature = 0.2

# Maximum tokens in the response
max_tokens = 500

# Number of retry attempts on failure
max_retries = 2

# --- Debugging ---
# Enable LiteLLM debug logging (true/false)
debug = false
```

## Troubleshooting

-   **`doit: command not found`**: Make sure `~/.local/bin` is in your `$PATH`. Add `export PATH="$HOME/.local/bin:$PATH"` to your `~/.bashrc` and restart your shell.
-   **`Configuration file not found`**: Ensure you have copied `doit.cfg` to `~/doit.cfg` (or `.doit.cfg`).
-   **API Authentication Errors**: Double-check that your API key is exported correctly as an environment variable (e.g., `OPENAI_API_KEY`).
-   **Local Model Not Responding**: Make sure the Ollama server is running. You can test it with `ollama list`.


### Verbose Mode

For debugging, use `-v` to see:
- Raw LLM response
- Parsed JSON structure
- Safety check results

```bash
doit -v "list the files"
```

## How It Works

### Architecture

```
1. CLI Input
   ↓
2. LLM Call (provider-aware)
    - API or tool-capable local models try tool/structured output first
    - General local instruction models fall back to prompt-only JSON
   ↓
3. Response Parsing
   - Extracts JSON from LLM output
   - Validates schema (command/answer/not_possible)
   ↓
4. Safety Check
   - Detects dangerous patterns (rm -rf, sudo, etc.)
   - Requests user confirmation if needed
   ↓
5. Command Execution
   - Runs bash command with 20-second timeout
   - Captures stdout, stderr, exit code
   ↓
6. Output Display
```

### Response Types

The LLM returns one of three structured JSON types:

#### 1. Command Response
Execute a shell command:
```json
{
  "type": "command",
  "command": "ls ~/Documents",
  "explanation": "Lists all files in the Documents folder"
}
```

#### 2. Answer Response
Conversational response (no execution):
```json
{
  "type": "answer",
  "answer": "I can help you manage files, run commands, and more."
}
```

#### 3. Not Possible Response
Task cannot be done in shell:
```json
{
  "type": "not_possible",
  "answer": "That's a complex task requiring Python programming. I can't do it as a bash command."
}
```

## Project Structure

```
.
├── doit.py                 # Entry point (compatibility wrapper)
├── pyproject.toml          # uv project configuration and dependencies
├── setup.sh                # Installation script (sets up uv virtualenv and wrapper)
├── test.sh                 # Test script running in uv environment
└── doit/
    ├── __init__.py
    ├── main.py             # Main CLI orchestrator
    ├── llm.py              # LLM integration (LiteLLM with OpenAI/Gemini/Claude support)
    ├── response_parser.py  # JSON parsing & validation
    ├── safety.py           # Dangerous command detection and confirmation
    └── command_executor.py # Bash execution with cd command state tracking
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `llm.py` | Send prompts to OpenAI API, handle retries |
| `response_parser.py` | Parse JSON, validate schema, extract data |
| `safety.py` | Detect dangerous patterns, request confirmation |
| `command_executor.py` | Run bash, capture output, enforce 20s timeout |
| `doit.py` | Orchestrate: parse args → LLM → safety → execute |

## Error Handling

### API Errors

If OpenAI API fails:
```
[WARNING] API error (attempt 1): Connection timeout
[WARNING] API error (attempt 2): Rate limit exceeded
[ERROR] Failed after 2 attempts: Rate limit exceeded
Error: Could not get response from LLM. Please check your API key and network connection.
```

### Invalid JSON

If LLM response is malformed:
```
Error: Could not parse LLM response: Invalid JSON in response: Expecting value
```

### Malformed Commands

If command is invalid:
```
⛔ Command is empty or malformed.
```

## Examples

### Example 1: List files
```bash
$ doit "show me all python files in my home directory"
🤔 Thinking...

💡 Lists all Python files in the home directory
📍 Executing: find ~ -maxdepth 1 -name "*.py" -type f

Exit code: 0

--- STDOUT ---
/home/user/script.py
/home/user/test.py
```

### Example 2: System info
```bash
$ doit "how much disk space do I have left?"
🤔 Thinking...

💡 Shows disk space usage for all mounted filesystems
📍 Executing: df -h

Exit code: 0

--- STDOUT ---
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   20G   30G  40% /
```

### Example 3: Conversational response
```bash
$ doit "what does the ls command do?"
🤔 Thinking...

💡 The ls command lists files and directories in a directory.

(No output)
```

## Troubleshooting

### "Command not found: doit"

Add installation directory to PATH:
```bash
# If installed to ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

### "OPENAI_API_KEY not set"

Set your API key:
```bash
export OPENAI_API_KEY="sk-..."
```

### "Response parsing failed"

- LLM response might be malformed
- Try with simpler instruction
- Use verbose mode to debug: `doit -v "..."`

## Development

### Running Locally (Without Installation)

```bash
cd /path/to/LLM-EX3
export GEMINI_API_KEY="your-gemini-key"
uv run doit.py "list my files"
```

### Verbose Output for Debugging

```bash
uv run doit.py -v "your instruction"
```

Shows:
- Raw LLM response
- Parsed response structure
- Safety check results




