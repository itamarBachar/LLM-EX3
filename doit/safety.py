"""
Safety module for detecting and preventing dangerous shell commands.

Responsibilities:
- Identify dangerous command patterns
- Request user confirmation for risky operations
- Prevent accidental data destruction
"""

import re
import sys
from typing import Tuple


# Dangerous patterns that require confirmation
DANGEROUS_PATTERNS = [
    # Destructive operations
    (r"\brm\s+(-r|-rf|-f|--recursive|--force)", "rm with recursive/force flag"),
    (r"\brmdir\b", "directory removal"),
    (r"\bmkfs\b", "filesystem format"),
    (r"\bdd\s+of=", "disk/partition write (dd)"),
    (r"\bshred\b", "secure file deletion"),
    (r">", "output redirection (could overwrite files)"),  # Be careful with this
    
    # Permission changes
    (r"\bchmod\s+.*777\b", "chmod 777 (unrestricted permissions)"),
    (r"\bchown\b", "ownership change"),
    (r"\bchgrp\b", "group change"),
    
    # System modifications
    (r"\bsudo\b", "sudo (requires elevated privileges)"),
    (r"\b(systemctl|service)\s+(stop|restart|disable)\b", "system service control"),
    (r"\b(reboot|shutdown|halt|poweroff)\b", "system shutdown/reboot"),
    
    # Package manager (can break system)
    (r"\b(apt|apt-get|yum|pacman)\s+(remove|purge|uninstall|autoremove)\b", "package removal"),
    (r"\bpip\s+uninstall\b", "pip package removal"),
    
    # Code injection patterns
    (r"\bcurl\s+.*\|\s*bash\b", "curl piped to bash (code execution)"),
    (r"\bwget\s+.*\|\s*bash\b", "wget piped to bash (code execution)"),
    (r"\beval\b", "eval (code execution)"),
    (r"\bexec\b", "exec (process replacement)"),
    
    # Database operations (destructive)
    (r"DROP\s+DATABASE\b", "SQL database drop"),
    (r"DELETE\s+FROM\b", "SQL record deletion"),
    (r"\btruncate\b", "table truncation"),
]


def detect_dangerous_patterns(command: str) -> Tuple[bool, str]:
    """
    Detect dangerous patterns in a shell command.
    
    Args:
        command: Shell command to check.
        
    Returns:
        Tuple of (is_dangerous: bool, reason: str).
    """
    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, description
    return False, ""


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
    print(f"\n⚠️  DANGEROUS OPERATION DETECTED: {reason}")
    print("Command execution could cause data loss or system damage.")
    
    try:
        user_input = input("Do you want to proceed? (yes/no): ").strip().lower()
        return user_input in ("yes", "y")
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        return False


def should_execute_command(command: str) -> Tuple[bool, str]:
    """
    Determine if a command should be executed.
    
    Checks for:
    1. Malformed/empty commands
    2. Dangerous patterns (requires confirmation if found)
    
    Args:
        command: Shell command to evaluate.
        
    Returns:
        Tuple of (should_execute: bool, message: str).
    """
    # Check if command is valid
    if is_empty_or_malformed(command):
        return False, "Command is empty or malformed."
    
    # Check for dangerous patterns
    is_dangerous, reason = detect_dangerous_patterns(command)
    
    if is_dangerous:
        confirmed = request_confirmation(reason)
        if not confirmed:
            return False, f"User cancelled dangerous operation: {reason}"
        return True, f"User confirmed dangerous operation: {reason}"
    
    return True, "Safe to execute."
