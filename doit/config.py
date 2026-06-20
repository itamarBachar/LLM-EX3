"""
Configuration module for DoIt.

Responsibilities:
- Load and parse doit.cfg from home directory
- Provide unified config access
- Handle missing or invalid configuration
"""

import os
import sys
from pathlib import Path
from configparser import ConfigParser
from typing import Literal, Optional


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


class DoItConfig:
    """Configuration handler for DoIt."""
    
    # Valid provider options
    VALID_PROVIDERS = {"api", "local_no_tools", "local_with_tools"}
    
    def __init__(self):
        """Initialize configuration from first found doit.cfg."""
        self.config = ConfigParser()
        self.config_path = self._find_config_path()
        self._load_config()
    
    def _find_config_path(self) -> Path:
        """Find configuration file using fallback search paths."""
        project_root = Path(__file__).resolve().parent.parent
        search_paths = [
            Path.cwd() / "doit.cfg",
            Path.cwd() / ".doit.cfg",
            Path.home() / "doit.cfg",
            Path.home() / ".doit.cfg",
            project_root / "doit.cfg",
            project_root / "doit" / "doit.cfg",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
                
        # If none exist, we raise ConfigError listing options
        raise ConfigError(
            f"Configuration file 'doit.cfg' or '.doit.cfg' not found in any of the search paths:\n"
            f"  - {', '.join(str(p) for p in search_paths)}\n"
            "Please ensure a configuration file is present."
        )
    
    def _load_config(self) -> None:
        """Load and validate configuration file."""
        self.config.read(self.config_path)
        
        if "model" not in self.config:
            raise ConfigError(
                f"Missing [model] section in {self.config_path}"
            )
    
    def get_provider(self) -> Literal["api", "local_no_tools", "local_with_tools"]:
        """Get the configured model provider."""
        provider = self.config.get("model", "provider", fallback="api").strip()
        
        if provider not in self.VALID_PROVIDERS:
            raise ConfigError(
                f"Invalid provider '{provider}'. "
                f"Must be one of: {', '.join(self.VALID_PROVIDERS)}"
            )
        
        return provider  # type: ignore
    
    def get_model_name(self) -> str:
        """Get the model name based on current provider."""
        provider = self.get_provider()
        
        if provider == "api":
            model = self.config.get("model", "api_model", fallback="gpt-4o-mini").strip()
        elif provider == "local_no_tools":
            model = self.config.get("model", "local_model_no_tools", fallback="ollama/gemma3:4b").strip()
        else:  # local_with_tools
            model = self.config.get("model", "local_model_with_tools", fallback="ollama/qwen3:4b-instruct").strip()
        
        if not model:
            raise ConfigError(f"No model specified for provider '{provider}'")
        
        return model
    
    def get_temperature(self) -> float:
        """Get temperature setting."""
        temp = self.config.getfloat("model", "temperature", fallback=0.2)
        if not 0 <= temp <= 1:
            raise ConfigError("Temperature must be between 0 and 1")
        return temp
    
    def get_max_tokens(self) -> int:
        """Get max tokens setting."""
        return self.config.getint("model", "max_tokens", fallback=500)
    
    def get_max_retries(self) -> int:
        """Get max retries setting."""
        return self.config.getint("model", "max_retries", fallback=2)
    
    def is_debug(self) -> bool:
        """Check if debug logging is enabled."""
        return self.config.getboolean("model", "debug", fallback=False)

    def is_history_enabled(self) -> bool:
        """Whether multi-turn history is recorded and fed back to the model."""
        return self.config.getboolean("history", "enabled", fallback=True)

    def get_history_limit(self) -> int:
        """How many recent turns to include as context on each invocation."""
        return self.config.getint("history", "max_turns", fallback=10)

    def is_memory_enabled(self) -> bool:
        """Whether persistent memory is enabled."""
        if "memory" in self.config:
            return self.config.getboolean("memory", "enabled", fallback=True)
        return True
    
    def has_tool_calling_support(self) -> bool:
        """Check if the current model supports tool calling."""
        provider = self.get_provider()
        return provider == "local_with_tools" or provider == "api"
    
    def summary(self) -> str:
        """Get a summary of current configuration."""
        provider = self.get_provider()
        model = self.get_model_name()
        return f"Provider: {provider} | Model: {model}"


def get_config() -> DoItConfig:
    """Get or create the global configuration instance."""
    if not hasattr(get_config, "_instance"):
        get_config._instance = DoItConfig()
    return get_config._instance
