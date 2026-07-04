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
from typing import Dict, Any, Optional, Tuple


def is_navigation_command(command: str) -> Optional[Tuple[str, str]]:
    """
    Check if the command is a navigation command (cd, pushd, popd).
    
    Returns:
        A tuple of (cmd_name, arguments_str) if it matches, else None.
    """
    cleaned = command.strip()
    parts = cleaned.split(None, 1)
    if not parts:
        return None
        
    cmd_name = parts[0]
    if cmd_name not in ("cd", "pushd", "popd"):
        return None
        
    args_str = parts[1].strip() if len(parts) > 1 else ""
    return cmd_name, args_str


def parse_navigation_path(args_str: str) -> str:
    """
    Resolve and clean the target directory path by stripping quotes,
    expanding tildes (~), and expanding environment variables.
    """
    if not args_str:
        return os.path.expanduser("~")
        
    # Strip matching leading and trailing quotes if present
    if (args_str.startswith('"') and args_str.endswith('"')) or (args_str.startswith("'") and args_str.endswith("'")):
        args_str = args_str[1:-1]
        
    # Expand tilde (~) and environment variables (e.g. $VAR)
    expanded = os.path.expandvars(os.path.expanduser(args_str.strip()))
    return os.path.abspath(expanded)


def execute_process_navigation(cmd_name: str, target_path: str) -> None:
    """
    Apply directory navigation to the current Python process context.
    This ensures subsequent commands in the same execution run in the updated CWD.
    """
    if cmd_name in ("cd", "pushd"):
        if os.path.exists(target_path):
            os.chdir(target_path)


def write_shell_navigation(shell_cmd: str) -> None:
    """
    Write the navigation command to DOIT_CD_FILE so the parent shell can execute it.
    """
    cd_file = os.environ.get("DOIT_CD_FILE")
    if cd_file:
        try:
            with open(cd_file, "w", encoding="utf-8") as f:
                f.write(shell_cmd)
        except Exception:
            pass


def handle_navigation_command(command: str) -> Optional[Dict[str, Any]]:
    """
    Identify and execute navigation commands natively in the Python process
    and propagate them to the parent shell.
    
    Returns:
        A dict with returncode and output if handled, else None if not a navigation command.
    """
    nav_info = is_navigation_command(command)
    if nav_info is None:
        return None
        
    cmd_name, args_str = nav_info
    
    # 1. Resolve target path (only needed for cd, and pushd with args)
    target_path = ""
    if cmd_name in ("cd", "pushd"):
        if cmd_name == "cd" or args_str:
            target_path = parse_navigation_path(args_str)
            if not os.path.exists(target_path):
                return {
                    "stdout": "",
                    "stderr": f"{cmd_name}: no such file or directory: {args_str}",
                    "returncode": 1,
                    "timeout": False,
                }
                
    # 2. Change current Python process directory
    if target_path:
        try:
            execute_process_navigation(cmd_name, target_path)
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"{cmd_name}: {str(e)}",
                "returncode": 1,
                "timeout": False,
            }
            
    # 3. Propagate to parent shell
    write_shell_navigation(command.strip())
    
    return {
        "stdout": "",
        "stderr": "",
        "returncode": 0,
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
    nav_result = handle_navigation_command(command)
    if nav_result is not None:
        return nav_result

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


def execute_and_display(command: str) -> Tuple[int, str, str]:
    """
    Execute a command and display formatted output.

    Args:
        command: Shell command to execute.

    Returns:
        A tuple containing (exit code, stdout, stderr).
    """
    print(f"\n📍 Executing: {command}\n")

    result = run_shell_command(command)
    output = format_command_output(result)

    print(output)
    print()

    return result["returncode"], result["stdout"], result["stderr"]
