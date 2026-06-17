"""
Command executor module for running bash commands safely.

Responsibilities:
- Execute shell commands with subprocess
- Capture stdout, stderr, return codes
- Enforce timeout limits
- Handle execution errors gracefully
"""

import os
import subprocess
import sys
from typing import Dict, Any, Optional


def handle_cd_command(command: str) -> Optional[Dict[str, Any]]:
    """
    Handle cd commands natively in Python.
    Changes the directory of the current process and writes to DOIT_CD_FILE
    if it is configured in the environment, so the parent shell can navigate.
    """
    cleaned = command.strip()
    
    # Check if it's a simple cd command (no metacharacters)
    if not ((cleaned.startswith("cd ") or cleaned == "cd") and not any(char in cleaned for char in ["&&", ";", "|", ">", "<"])):
        return None
        
    parts = cleaned.split(None, 1)
    if len(parts) == 1:
        target_dir = os.path.expanduser("~")
        path_str = "~"
    else:
        path_str = parts[1].strip()
        # Strip matching quotes if present
        if (path_str.startswith('"') and path_str.endswith('"')) or (path_str.startswith("'") and path_str.endswith("'")):
            path_str = path_str[1:-1]
        target_dir = os.path.expanduser(path_str)
        
    try:
        target_dir = os.path.abspath(target_dir)
        if not os.path.exists(target_dir):
            return {
                "stdout": "",
                "stderr": f"cd: no such file or directory: {path_str}",
                "returncode": 1,
                "timeout": False,
            }
            
        # Change current directory of the Python process itself
        os.chdir(target_dir)
        
        # If running in a shell wrapper that set DOIT_CD_FILE, write to it
        cd_file = os.environ.get("DOIT_CD_FILE")
        if cd_file:
            try:
                with open(cd_file, "w") as f:
                    f.write(target_dir)
            except Exception:
                pass
                
        return {
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "timeout": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"cd: {str(e)}",
            "returncode": 1,
            "timeout": False,
        }


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
    # Try handling cd natively
    cd_result = handle_cd_command(command)
    if cd_result is not None:
        return cd_result

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
