"""
Safety module for detecting and preventing dangerous shell commands.

Responsibilities:
- Identify dangerous command patterns
- Request user confirmation for risky operations
- Prevent accidental data destruction
"""

import sys
from typing import Tuple

from doit.llm import assess_command_risk_with_llm

def detect_filesystem_modification(command: str) -> Tuple[bool, str]:
    """
    Use the configured LLM to decide whether a command modifies the filesystem
    and therefore requires explicit confirmation before execution.
    """
    try:
        return assess_command_risk_with_llm(
            command,
            include_filesystem_modifications=True,
        )
    except Exception as e:
        print(f"[WARNING] LLM filesystem check failed: {str(e)}")
        return False, "LLM filesystem check unavailable"


def is_empty_or_malformed(command: str) -> bool:
    """Check if command is empty or obviously malformed."""
    stripped = command.strip()
    if not stripped:
        return True
    
    # Check for unclosed quotes
    if stripped.count('"') % 2 != 0:
        return True
    if stripped.count("'") % 2 != 0:
        return True
    
    return False


def request_confirmation(reason: str) -> bool:
    """
    Request user confirmation for dangerous operation.
    
    Args:
        reason: Description of the danger.
        
    Returns:
        True if user confirmed, False otherwise.
    """
    print(f"\n⚠️  Confirmation required: {reason}")
    print("This command will not run unless you explicitly approve it.")
    
    if not sys.stdin.isatty():
        print("Non-interactive terminal detected. Skipping dangerous command execution for safety.")
        return False
    
    try:
        user_input = input("Proceed? Type 'y' to run it: ").strip().lower()
        return user_input == "y"
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        return False


def should_execute_command(command: str) -> Tuple[bool, str]:
    """
    Determine if a command should be executed.
    
    Checks for:
    1. Malformed or empty commands
    2. Filesystem modifications (requires confirmation)
    
    Args:
        command: Shell command to evaluate.
        
    Returns:
        Tuple of (should_execute: bool, message: str).
    """
    # Check if command is valid
    if is_empty_or_malformed(command):
        return False, "Command is empty or malformed."
    
    modifies_filesystem, reason = detect_filesystem_modification(command)
    if modifies_filesystem:
        confirmation_reason = f"filesystem modification detected: {reason}"
        confirmed = request_confirmation(confirmation_reason)
        if not confirmed:
            return False, f"User declined filesystem-modifying command: {confirmation_reason}"
        return True, f"User confirmed filesystem-modifying command: {confirmation_reason}"
    
    return True, "Read-only command; safe to execute directly."
