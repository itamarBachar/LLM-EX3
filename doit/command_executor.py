"""
Command executor module for running bash commands safely.

Responsibilities:
- Execute shell commands with subprocess
- Capture stdout, stderr, return codes
- Enforce timeout limits
- Handle execution errors gracefully
"""

import subprocess
import sys
from typing import Dict, Any


def run_shell_command(command: str, shell: str = "/bin/bash", timeout: int = 20) -> Dict[str, Any]:
    """
    Execute a shell command and capture output.
    
    Args:
        command: Shell command to execute.
        shell: Shell executable path (default: /bin/bash).
        timeout: Maximum execution time in seconds (default: 20).
        
    Returns:
        Dictionary with:
        - stdout: Command output
        - stderr: Error output
        - returncode: Exit code
        - timeout: Whether command timed out
    """
    result = {
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "timeout": False,
    }
    
    try:
        proc_result = subprocess.run(
            command,
            shell=True,
            executable=shell,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        
        result["stdout"] = proc_result.stdout
        result["stderr"] = proc_result.stderr
        result["returncode"] = proc_result.returncode
        result["timeout"] = False
        
    except subprocess.TimeoutExpired as e:
        result["stderr"] = f"Command timed out after {timeout} seconds"
        result["returncode"] = -1
        result["timeout"] = True
        
        # Try to capture partial output
        if e.stdout:
            result["stdout"] = e.stdout
        if e.stderr:
            result["stderr"] += f"\n{e.stderr}" if result["stderr"] else e.stderr
    
    except Exception as e:
        result["stderr"] = f"Execution error: {str(e)}"
        result["returncode"] = -1
    
    return result


def format_command_output(result: Dict[str, Any]) -> str:
    """
    Format command execution result for display.
    
    Args:
        result: Result dictionary from run_shell_command().
        
    Returns:
        Formatted output string.
    """
    lines = []
    
    if result["timeout"]:
        lines.append("⏱️  TIMEOUT: Command exceeded 20 second limit")
    
    lines.append(f"Exit code: {result['returncode']}")
    
    if result["stdout"]:
        lines.append("\n--- STDOUT ---")
        lines.append(result["stdout"])
    
    if result["stderr"]:
        lines.append("\n--- STDERR ---")
        lines.append(result["stderr"])
    
    if not result["stdout"] and not result["stderr"]:
        lines.append("(No output)")
    
    return "\n".join(lines)


def execute_and_display(command: str) -> int:
    """
    Execute a command and display formatted output.
    
    Args:
        command: Shell command to execute.
        
    Returns:
        Exit code of the command.
    """
    print(f"\n📍 Executing: {command}\n")
    
    result = run_shell_command(command)
    output = format_command_output(result)
    
    print(output)
    print()
    
    return result["returncode"]
