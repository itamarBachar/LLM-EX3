"""
LLM interaction module using LiteLLM for multi-provider support.

Responsibilities:
- Send natural language instructions to LLM via LiteLLM
- Request structured JSON responses
- Handle API errors gracefully
- Support multiple model providers and local models
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import os
import litellm
from doit.config import get_config, ConfigError, DoItConfig
from doit.response_parser import extract_json_from_response


SYSTEM_PROMPT = """
You are a bash command expert that converts natural language instructions into bash commands.

You must choose exactly one response type:

1. command:
Use this when the user asks for something that can be executed in bash.

2. not_possible:
Use this when the user request is not a bash command (e.g. conversational requests, greetings, jokes, help questions, or things that cannot reasonably be done with a standard bash command).

Rules:
- For 'command', return the command in the 'command' field and explain it in the 'explanation' field.
- For 'not_possible', return null in the 'command' field and write a polite, helpful response in the 'explanation' field (e.g., explain that you are a bash command expert and cannot fulfill that request).
- Use bash syntax.
- Return only one command.
- Avoid sudo unless absolutely necessary.
- Prefer safe read-only commands when possible.
- If the command modifies files, still return the command. Safety confirmation is handled by the program.
- Do not include markdown.
- Do not include text outside the JSON object.
"""


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["command", "not_possible"],
        },
        "command": {
            "type": ["string", "null"],
        },
        "explanation": {
            "type": ["string", "null"],
        },
    },
    "required": ["type", "command", "explanation"],
    "additionalProperties": False,
}


SINGLE_SHOT_BASH_RESPONSE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_bash_command",
        "description": "Return either one bash command for the user request, or explain why the request is not possible as a bash command.",
        "parameters": RESPONSE_SCHEMA,
    },
}


def _normalize_bash_response(data: dict) -> str:
    """Normalize parsed model output to the JSON string expected by the rest of the program."""
    response_type = data.get("type")

    if response_type == "command":
        command = data.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Tool response type is 'command' but command is empty")

        explanation = data.get("explanation") or "Generated bash command."
        normalized = {
            "type": "command",
            "command": command.strip(),
            "explanation": str(explanation).strip(),
        }

    elif response_type == "not_possible":
        explanation = data.get("explanation") or data.get("answer")
        if not explanation:
            explanation = "This request cannot reasonably be converted into a bash command."

        normalized = {
            "type": "not_possible",
            "command": None,
            "explanation": str(explanation).strip(),
        }

    else:
        raise ValueError(f"Unsupported response type from LLM: {response_type}")

    return json.dumps(normalized, ensure_ascii=False)


def _build_bash_messages(instruction: str) -> List[Dict[str, str]]:
    """Build the shared chat message list for bash command generation."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": instruction},
    ]


def _extract_tool_call_arguments(response: Any) -> Dict[str, Any]:
    """Extract parsed arguments from the first tool call in a completion response."""
    message = response.choices[0].message
    if isinstance(message, dict):
        tool_calls = message.get("tool_calls")
    else:
        tool_calls = getattr(message, "tool_calls", None)

    if not tool_calls:
        raise ValueError("Model did not return a tool call")

    first_tool_call = tool_calls[0]
    function_call = (
        first_tool_call.get("function")
        if isinstance(first_tool_call, dict)
        else first_tool_call.function
    )
    arguments = (
        function_call.get("arguments")
        if isinstance(function_call, dict)
        else function_call.arguments
    )

    if isinstance(arguments, str):
        return json.loads(arguments)
    if isinstance(arguments, dict):
        return arguments

    raise ValueError("Tool call arguments are not valid JSON")


SAFETY_SYSTEM_PROMPT = """
You are a shell safety classifier.

Your task is to decide whether a shell command either:
- is high-risk and requires explicit user confirmation before execution, or
- modifies the filesystem and therefore requires explicit user confirmation before execution.

High-risk commands include operations that can damage the system, execute remote
code, alter services, write raw disks, reboot the machine, uninstall software,
or perform destructive database actions.

Do not mark a command as high-risk only because it reads files or prints
information. Unless the user explicitly asks you to include filesystem writes,
filesystem-creation, move, copy, delete, and redirection checks are handled
separately by the program, so focus on other risky behavior.

When the user asks you to include filesystem writes, answer yes for commands
that create, delete, move, copy, extract, truncate, edit in place, change file
permissions or ownership, or redirect output into files.

Return only valid JSON matching the schema.
"""


SAFETY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_dangerous": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["is_dangerous", "reason"],
    "additionalProperties": False,
}


def _supports_tool_calling(config: DoItConfig) -> bool:
    """Return whether the active model path should attempt tool calling first."""
    return config.has_tool_calling_support()


def _supports_structured_output(config: DoItConfig) -> bool:
    """Return whether the active model path should attempt JSON schema output."""
    return config.get_provider() != "local_no_tools"


def _get_completion_settings(config: DoItConfig) -> Tuple[str, float, int]:
    """Resolve the model and generation settings shared by LLM calls."""
    if config.is_debug():
        litellm.set_verbose(True)

    model_id = _get_litellm_model_id(config)
    _validate_api_keys(config, model_id)
    return model_id, config.get_temperature(), config.get_max_tokens()


def _get_litellm_model_id(config: DoItConfig) -> str:
    """
    Get the model ID in LiteLLM format.
    
    LiteLLM format:
    - API models: "provider/model" (e.g., "openai/gpt-4o-mini")
    - Local models: "model_name" (e.g., "ollama/gemma3:4b", "ollama/qwen3:4b-instruct")
    """
    provider = config.get_provider()
    model_name = config.get_model_name()
    
    if provider == "api":
        # For API models, prepend provider if not already included
        if "/" not in model_name:
            if model_name.startswith("gemini"):
                return f"gemini/{model_name}"
            elif model_name.startswith("claude"):
                return f"anthropic/{model_name}"
            # Assume OpenAI if no provider specified
            return f"openai/{model_name}"
        return model_name
    else:
        # For local models, use as-is or with ollama prefix
        if "/" in model_name:
            return model_name
        # Default to ollama for local models
        return f"ollama/{model_name}"


def _validate_api_keys(config: DoItConfig, model_id: str) -> None:
    """Validate that required API keys are present in environment variables."""
    if config.get_provider() == "api":
        if model_id.startswith("gemini/") and not os.environ.get("GEMINI_API_KEY"):
            raise Exception("GEMINI_API_KEY environment variable is not set. Please set it before using Gemini models.")
        elif model_id.startswith("openai/") and not os.environ.get("OPENAI_API_KEY"):
            raise Exception("OPENAI_API_KEY environment variable is not set. Please set it before using OpenAI models.")
        elif (model_id.startswith("anthropic/") or model_id.startswith("claude")) and not os.environ.get("ANTHROPIC_API_KEY"):
            raise Exception("ANTHROPIC_API_KEY environment variable is not set. Please set it before using Claude models.")


def call_llm_for_bash_single_shot(instruction: str) -> str:
    """
    Send a natural language instruction through the current single-shot tool-forced path.

    This uses a schema-like pseudo-tool to force one structured response and then
    normalizes that payload into the JSON shape used by the rest of the program:
    {"type": "command" | "not_possible", "command": str | None, "explanation": str}
    """
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)

    try:
        response = litellm.completion(
            model=model_id,
            messages=_build_bash_messages(instruction),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=[SINGLE_SHOT_BASH_RESPONSE_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "generate_bash_command"},
            },
        )
        parsed = _extract_tool_call_arguments(response)
        return _normalize_bash_response(parsed)

    except litellm.APIError as e:
        raise Exception(f"LiteLLM API error during tool call: {str(e)}")
    except litellm.AuthenticationError as e:
        raise Exception(f"Authentication error during tool call: {str(e)}")
    except (KeyError, json.JSONDecodeError, ValueError) as e:
        raise Exception(f"Malformed tool call response from LLM: {str(e)}")
    except Exception as e:
        raise Exception(f"LiteLLM tool call error: {str(e)}")


def call_llm_for_bash_toolcalling(instruction: str) -> str:
    """Backward-compatible wrapper for the current single-shot tool-forced path."""
    return call_llm_for_bash_single_shot(instruction)


def call_llm_for_bash_tool_loop(instruction: str) -> str:
    """
    Placeholder entry point for a future multi-turn host-executed tool loop.

    This will eventually own the orchestration of real tool calls and still
    return the same final normalized JSON string consumed by the CLI.
    """
    raise NotImplementedError("Multi-turn tool loop is not implemented yet.")


def call_llm_for_bash(instruction: str) -> str:
    """
    Send a natural language instruction to the LLM and get structured JSON response.
    Uses LiteLLM to support multiple model providers.
    
    Returns:
        Raw JSON string from the LLM.
        
    Raises:
        Exception: If API call fails or configuration is invalid.
    """
    config = get_config()
    
    model_id, temperature, max_tokens = _get_completion_settings(config)
    
    try:
        # Use LiteLLM's completion endpoint
        # This works with API models and local models (via ollama)
        response = litellm.completion(
            model=model_id,
            messages=_build_bash_messages(instruction),
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "bash_response",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA
                }
            },
        )
        
        return response.choices[0].message.content.strip()
    
    except litellm.APIError as e:
        raise Exception(f"LiteLLM API error: {str(e)}")
    except litellm.AuthenticationError as e:
        raise Exception(f"Authentication error (check API keys): {str(e)}")
    except Exception as e:
        raise Exception(f"LiteLLM error: {str(e)}")


def call_llm_for_bash_prompt_fallback(instruction: str) -> str:
    """
    Fallback for models or API versions where json_object structured output fails.
    Uses prompt-based JSON generation instead.
    """
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)

    fallback_prompt = f"""
    Return only valid JSON.

    Allowed formats:

    Command:
    {{
    "type": "command",
    "command": "the bash command",
    "explanation": "brief explanation"
    }}

    Not possible:
    {{
    "type": "not_possible",
    "command": null,
    "explanation": "why it is not possible as a bash command"
    }}

    User instruction:
    {instruction}
    """

    response = litellm.completion(
        model=model_id,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": fallback_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content.strip()
    return _normalize_bash_response(extract_json_from_response(content))


def call_llm_with_fallback(
    instruction: str,
    max_retries: int = 2,
) -> Optional[str]:
    """
    Try tool calling first, then structured JSON output, then prompt-based JSON.

    This keeps the public return value unchanged: a JSON string with
    type, command, and explanation fields.
    """
    config = get_config()
    effective_retries = max_retries or config.get_max_retries()

    if _supports_tool_calling(config):
        for attempt in range(effective_retries):
            try:
                return call_llm_for_bash_single_shot(instruction)
            except ConfigError as e:
                print(f"[ERROR] Configuration error: {str(e)}")
                return None
            except Exception as e:
                if attempt < effective_retries - 1:
                    print(f"[WARNING] Tool calling failed (attempt {attempt + 1}): {str(e)}")
                    continue

                print("[WARNING] Tool calling failed. Trying structured JSON output.")

    if _supports_structured_output(config):
        try:
            return call_llm_for_bash(instruction)
        except ConfigError as e:
            print(f"[ERROR] Configuration error: {str(e)}")
            return None
        except Exception as structured_error:
            print(f"[WARNING] Structured output failed: {str(structured_error)}")
            print("[WARNING] Trying prompt-based JSON fallback.")

    try:
        return call_llm_for_bash_prompt_fallback(instruction)
    except Exception as fallback_error:
        print(f"[ERROR] Fallback failed: {str(fallback_error)}")
        return None


def _build_safety_prompt(
    command: str,
    include_filesystem_modifications: bool,
) -> str:
    """Build the user prompt for shell safety classification."""
    if include_filesystem_modifications:
        return (
            "Classify whether this shell command modifies the filesystem and therefore requires confirmation. "
            "Answer true for file or directory creation, deletion, moves, copies, extraction, in-place edits, permission changes, or shell redirection into files.\n\n"
            f"Command: {command}"
        )

    return (
        "Classify this shell command for safety. "
        "Ignore simple filesystem create, copy, move, delete, or redirection behavior, "
        "because those are checked separately.\n\n"
        f"Command: {command}"
    )


def _normalize_safety_response(parsed: Dict[str, Any]) -> Tuple[bool, str]:
    """Validate and normalize a parsed safety response."""
    if "is_dangerous" not in parsed:
        raise KeyError("is_dangerous")

    reason = str(parsed.get("reason") or "No reason provided.").strip()
    return bool(parsed["is_dangerous"]), reason


def _call_llm_for_safety_structured(
    command: str,
    include_filesystem_modifications: bool,
) -> Tuple[bool, str]:
    """Use schema-constrained output for safety classification."""
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)
    prompt = _build_safety_prompt(command, include_filesystem_modifications)

    response = litellm.completion(
        model=model_id,
        messages=[
            {"role": "system", "content": SAFETY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "command_safety_response",
                "strict": True,
                "schema": SAFETY_RESPONSE_SCHEMA,
            },
        },
    )

    content = response.choices[0].message.content.strip()
    return _normalize_safety_response(json.loads(content))


def _call_llm_for_safety_prompt_fallback(
    command: str,
    include_filesystem_modifications: bool,
) -> Tuple[bool, str]:
    """Fallback safety classification for models without tool calling or schema support."""
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)
    prompt = _build_safety_prompt(command, include_filesystem_modifications)

    fallback_prompt = (
        "Return only valid JSON in this format:\n"
        '{"is_dangerous": true, "reason": "brief reason"}\n\n'
        f"{prompt}"
    )

    response = litellm.completion(
        model=model_id,
        messages=[
            {"role": "system", "content": SAFETY_SYSTEM_PROMPT},
            {"role": "user", "content": fallback_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content.strip()
    return _normalize_safety_response(extract_json_from_response(content))


def assess_command_risk_with_llm(
    command: str,
    include_filesystem_modifications: bool = False,
) -> Tuple[bool, str]:
    """
    Ask the configured LLM whether a shell command is high-risk, or when
    requested, whether it modifies the filesystem.

    Args:
        command: Shell command to classify.
        include_filesystem_modifications: When True, let the LLM consider
            ordinary filesystem writes as part of the risk decision.

    Returns:
        Tuple of (is_dangerous, reason).

    Raises:
        Exception: If the model call fails or returns malformed JSON.
    """
    config = get_config()

    try:
        if _supports_structured_output(config):
            return _call_llm_for_safety_structured(
                command,
                include_filesystem_modifications,
            )

        return _call_llm_for_safety_prompt_fallback(
            command,
            include_filesystem_modifications,
        )

    except litellm.APIError as e:
        raise Exception(f"LiteLLM API error during safety check: {str(e)}")
    except litellm.AuthenticationError as e:
        raise Exception(f"Authentication error during safety check: {str(e)}")
    except (KeyError, json.JSONDecodeError) as e:
        raise Exception(f"Malformed safety response from LLM: {str(e)}")
    except Exception as e:
        raise Exception(f"LiteLLM safety check error: {str(e)}")
