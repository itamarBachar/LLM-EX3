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
import re
import litellm
from doit.config import get_config, ConfigError, DoItConfig
from doit.response_parser import (
    extract_json_from_response,
    parse_llm_response,
    ResponseParseError,
)
from doit.history_tracker import load_recent_shell_history, format_shell_history_for_prompt


SYSTEM_PROMPT = """
You are a helpful shell assistant. You can either run bash commands for the
user or answer their questions in plain language.

You must choose exactly one response type:

1. command:
Use this when the user wants an action performed now in the shell (e.g. "list
the files", "delete the logs", "show disk usage"). Return the command to run.

2. answer:
Use this when the user is asking a QUESTION or wants information, an
explanation, or conversation rather than an action — for example "how do I
find large files?", "what does chmod 755 mean?", "what can you do?", or "tell
me a joke". Write a helpful, direct answer in the 'answer' field. You may
include example commands inside the answer text, but they are NOT executed —
this response only informs the user. Be genuinely useful and friendly.

3. clarification:
Use this ONLY when the request is genuinely ambiguous and you cannot produce a
correct command without more information from the user (for example "sort by
date" could mean creation date vs. access date vs. modification date). Ask a
single, concrete question and, when the choices are known, offer a short list
of options. Do NOT use this for requests you can reasonably fulfill with a
sensible default — prefer producing a command in that case.

4. not_possible:
Use this only when the request genuinely cannot be helped with — it is neither
a shell action nor a question you can answer (e.g. it is harmful or completely
out of scope). Put a polite explanation in the 'explanation' field. Prefer
'answer' over 'not_possible' whenever you can say something useful.

Rules:
- For 'command', return the command in the 'command' field and explain it in the 'explanation' field.
- For 'answer', put your reply in the 'answer' field. Leave 'command' null.
- For 'clarification', put your question in the 'question' field and, when applicable, a list of choices in the 'options' field (otherwise an empty list). Leave 'command' null.
- For 'not_possible', return null in the 'command' field and a polite reason in the 'explanation' field.
- Use bash syntax.
- Return only one command.
- Avoid sudo unless absolutely necessary.
- Prefer safe read-only commands when possible.
- If the command modifies files, still return the command. Safety confirmation is handled by the program.
- Do not include markdown.
- Do not include text outside the JSON object.

Memory Rules:
You have access to persistent memories about the user/system (listed under "Persistent memories").
If the user's instruction provides new persistent facts or preferences, extract them into 'new_memories' as a list of clear, concise declarative statements (e.g. "The user's LLM class project folder is ~/school/llms/ass3").
Only save persistent facts (e.g. paths, aliases, preferences, configs) - do not save transient/one-off actions or command requests.
If a new fact contradicts or updates an existing memory, add the new fact to 'new_memories' and add the exact text of the old/outdated memory to 'forget_memories' so it can be removed.
Always return 'new_memories' and 'forget_memories' as lists (empty if no memories are learned or forgotten).

You may be given recent conversation history for the current session. The
user's new instruction can be a follow-up that refers to an earlier turn
(for example "now sort them by date", "no, i meant latest first", or "undo
that"). When it is a follow-up, build on the previous turn instead of starting
from scratch. In particular:
- "modify it to do Y" / "make it also do Z" means take the previous command (or
  the command you described in a previous answer) and return an updated
  'command'.
If the new instruction is unrelated to the history, ignore the history.

User Awareness (Recent Manual Shell Commands):
You may be provided with a list of recent manual shell commands executed by the user in their active terminal session.
Use this list to understand the user's current context (for instance, what directory they recently navigated to, what folders they created, or what scripts they ran manually).
If they ask questions like "what did I just do?" or "summarize my recent actions", construct a clear answer based on this list.
"""


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["command", "answer", "not_possible", "clarification"],
        },
        "command": {
            "type": ["string", "null"],
        },
        "explanation": {
            "type": ["string", "null"],
        },
        "answer": {
            "type": ["string", "null"],
        },
        "question": {
            "type": ["string", "null"],
        },
        "options": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "new_memories": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "forget_memories": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
    "required": [
        "type",
        "command",
        "explanation",
        "answer",
        "question",
        "options",
        "new_memories",
        "forget_memories",
    ],
    "additionalProperties": False,
}


SINGLE_SHOT_BASH_RESPONSE_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_bash_command",
        "description": "Return one bash command to run, a plain-language answer to a question, a clarifying question when the request is genuinely ambiguous, or a polite note when the request cannot be helped with.",
        "parameters": RESPONSE_SCHEMA,
    },
}


def _normalize_bash_response(data: dict) -> str:
    """Normalize parsed model output to the JSON string expected by the rest of the program."""
    response_type = data.get("type")

    # Extract memory fields
    new_memories = data.get("new_memories") or []
    forget_memories = data.get("forget_memories") or []

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

    elif response_type == "answer":
        answer = data.get("answer") or data.get("explanation")
        if not answer:
            raise ValueError("Tool response type is 'answer' but answer is empty")

        normalized = {
            "type": "answer",
            "command": None,
            "answer": str(answer).strip(),
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

    elif response_type == "clarification":
        question = data.get("question") or data.get("explanation")
        if not question:
            raise ValueError("Tool response type is 'clarification' but question is empty")

        options = data.get("options") or []
        if not isinstance(options, list):
            options = []

        normalized = {
            "type": "clarification",
            "command": None,
            "question": str(question).strip(),
            "options": [str(o).strip() for o in options if str(o).strip()],
        }

    else:
        raise ValueError(f"Unsupported response type from LLM: {response_type}")

    # Add memory fields to normalized output
    normalized["new_memories"] = new_memories
    normalized["forget_memories"] = forget_memories

    return json.dumps(normalized, ensure_ascii=False)


def _build_bash_messages(
    instruction: str,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Build the shared chat message list for bash command generation.

    When memory_context is provided it is appended to the system prompt.
    When history_context is provided it is appended to the system prompt so
    that all model paths (tool calling, structured output, prompt fallback)
    receive the same conversational context.
    """
    system_content = SYSTEM_PROMPT
    if memory_context:
        system_content = f"{system_content}\n\n{memory_context}"
    if history_context:
        system_content = f"{system_content}\n\n{history_context}"

    shell_cmds = load_recent_shell_history()
    shell_history_context = format_shell_history_for_prompt(shell_cmds)
    if shell_history_context:
        system_content = f"{system_content}\n\n{shell_history_context}"

    return [
        {"role": "system", "content": system_content},
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


def call_llm_for_bash_single_shot(
    instruction: str,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
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
            messages=_build_bash_messages(instruction, history_context, memory_context),
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


def call_llm_for_bash_toolcalling(
    instruction: str,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
    """Backward-compatible wrapper for the current single-shot tool-forced path."""
    return call_llm_for_bash_single_shot(instruction, history_context, memory_context)


def call_llm_for_bash_tool_loop(instruction: str) -> str:
    """
    Placeholder entry point for a future multi-turn host-executed tool loop.

    This will eventually own the orchestration of real tool calls and still
    return the same final normalized JSON string consumed by the CLI.
    """
    raise NotImplementedError("Multi-turn tool loop is not implemented yet.")


def call_llm_for_bash(
    instruction: str,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
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
            messages=_build_bash_messages(instruction, history_context, memory_context),
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


def call_llm_for_bash_prompt_fallback(
    instruction: str,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
    """
    Fallback for models or API versions where json_object structured output fails.
    Uses prompt-based JSON generation instead.
    """
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)

    system_content = SYSTEM_PROMPT
    if memory_context:
        system_content = f"{system_content}\n\n{memory_context}"
    if history_context:
        system_content = f"{system_content}\n\n{history_context}"

    shell_cmds = load_recent_shell_history()
    shell_history_context = format_shell_history_for_prompt(shell_cmds)
    if shell_history_context:
        system_content = f"{system_content}\n\n{shell_history_context}"

    fallback_prompt = f"""
    Return only valid JSON.

    Allowed formats:

    Command (the user wants an action run in the shell):
    {{
    "type": "command",
    "command": "the bash command",
    "explanation": "brief explanation",
    "new_memories": ["new fact to remember"] or null,
    "forget_memories": ["old fact to forget"] or null
    }}

    Answer (the user is asking a question or wants information/explanation/conversation):
    {{
    "type": "answer",
    "command": null,
    "answer": "a helpful, direct plain-language answer",
    "new_memories": ["new fact to remember"] or null,
    "forget_memories": ["old fact to forget"] or null
    }}

    Not possible (only when neither a command nor an answer can help):
    {{
    "type": "not_possible",
    "command": null,
    "explanation": "why it cannot be helped with",
    "new_memories": ["new fact to remember"] or null,
    "forget_memories": ["old fact to forget"] or null
    }}

    Clarification (use only when the request is genuinely ambiguous):
    {{
    "type": "clarification",
    "command": null,
    "question": "the single question to ask the user",
    "options": ["option 1", "option 2"],
    "new_memories": ["new fact to remember"] or null,
    "forget_memories": ["old fact to forget"] or null
    }}

    User instruction:
    {instruction}
    """

    strict_reminder = (
        "\n\nRespond with the JSON object ONLY. No markdown, no code fences, "
        "no language tags (such as ```bash), and no text before or after the JSON."
    )

    last_content = ""
    for attempt in range(2):
        prompt = fallback_prompt if attempt == 0 else fallback_prompt + strict_reminder
        response = litellm.completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        last_content = response.choices[0].message.content.strip()
        try:
            return _normalize_bash_response(extract_json_from_response(last_content))
        except ResponseParseError:
            continue

    # The model never produced JSON (common with small local models). If it
    # answered with a bare shell command, salvage it instead of failing. Whether
    # we treat that command as executable or as a suggestion depends on how the
    # user phrased the request (a question vs. an action).
    salvaged = _salvage_bare_command(last_content, instruction)
    if salvaged is not None:
        return _normalize_bash_response(salvaged)

    # Re-raise the parse error so the caller can surface a useful message.
    return _normalize_bash_response(extract_json_from_response(last_content))


_QUESTION_WORDS = (
    "how", "what", "why", "when", "where", "which", "who", "whom", "whose",
    "can", "could", "would", "should", "do", "does", "did", "is", "are",
    "am", "was", "were", "explain", "tell",
)


def _instruction_wants_action(instruction: str) -> bool:
    """
    Decide whether the user asked for an action to run vs. asked a question.

    Returns True when the request reads like an imperative action ("list the
    files", "find .txt files"), and False when it reads like a question or a
    request for information ("how do I find .txt files?"). When unclear we
    return False, because executing on an ambiguous request is the unsafe
    direction.
    """
    text = instruction.strip().lower()
    if not text:
        return False

    # A trailing question mark is a strong signal of a question.
    if text.endswith("?"):
        return False

    # Leading question words signal a question even without punctuation.
    first_word = re.split(r"[^a-z]+", text, maxsplit=1)[0]
    if first_word in _QUESTION_WORDS:
        return False

    return True


def _salvage_bare_command(
    content: str,
    instruction: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Recover a usable response from a non-JSON model reply that contains only a
    shell command, optionally wrapped in a Markdown code fence
    (e.g. ```bash\\n<command>\\n```).

    The recovered command is treated as executable only when ``instruction``
    reads like an action request; for questions (or when intent is unclear) it
    is returned as an *answer* suggestion so it is shown but never run. We reach
    this path because the model failed to follow the structured protocol, so the
    safe default is to inform rather than execute.

    Returns a command- or answer-shaped dict, or None when no plausible command
    is found.
    """
    text = content.strip()

    fence_match = re.search(r"```[a-zA-Z0-9]*\s*\n?([\s\S]*?)\n?```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Keep the first non-empty, non-comment line — a single command, not prose.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith("#")]
    if len(lines) != 1:
        return None

    command = lines[0]
    # Reject obvious prose: a real one-line command should not end with
    # sentence punctuation.
    if command.endswith((".", "?", "!", ":")):
        return None

    if _instruction_wants_action(instruction):
        return {
            "type": "command",
            "command": command,
            "explanation": "Recovered from a non-JSON model response.",
            "new_memories": [],
            "forget_memories": [],
        }

    return {
        "type": "answer",
        "command": None,
        "answer": f"You can use this command:\n\n    {command}",
        "new_memories": [],
        "forget_memories": [],
    }


def call_llm_with_fallback(
    instruction: str,
    max_retries: int = 2,
    history_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> Optional[str]:
    """
    Try tool calling first, then structured JSON output, then prompt-based JSON.

    This keeps the public return value unchanged: a JSON string with
    type, command, and explanation fields.

    Args:
        instruction: The user's natural language request.
        max_retries: Retries for the tool-calling path.
        history_context: Optional rendered conversation history to give the
            model context for follow-up instructions.
        memory_context: Optional rendered persistent memory context.
    """
    config = get_config()
    effective_retries = max_retries or config.get_max_retries()

    if _supports_tool_calling(config):
        for attempt in range(effective_retries):
            try:
                return call_llm_for_bash_single_shot(instruction, history_context, memory_context)
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
            structured_result = call_llm_for_bash(instruction, history_context, memory_context)
            # Local backends (e.g. Ollama) do not always honor json_schema and
            # may answer with markdown or prose instead of the required JSON.
            # Validate before trusting it; if it is not parseable, drop to the
            # prompt-based fallback rather than returning unusable content.
            parse_llm_response(structured_result)
            return structured_result
        except ConfigError as e:
            print(f"[ERROR] Configuration error: {str(e)}")
            return None
        except ResponseParseError as parse_error:
            print(f"[WARNING] Structured output was not valid JSON: {str(parse_error)}")
            print("[WARNING] Trying prompt-based JSON fallback.")
        except Exception as structured_error:
            print(f"[WARNING] Structured output failed: {str(structured_error)}")
            print("[WARNING] Trying prompt-based JSON fallback.")

    try:
        return call_llm_for_bash_prompt_fallback(instruction, history_context, memory_context)
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


def call_llm_for_history_summary(history_text: str) -> str:
    """
    Summarize a block of conversation history to compact it.
    
    Args:
        history_text: The string representation of older conversation turns.
        
    Returns:
        A concise summary string preserving user intent and context.
    """
    config = get_config()
    model_id, temperature, max_tokens = _get_completion_settings(config)
    
    system_prompt = (
        "You are an expert at summarizing shell conversation history. "
        "Your goal is to compact older conversation turns into a single, concise paragraph. "
        "Preserve important context: paths, files, user intents, preferences, and the outcome of commands. "
        "Do not list every command literally; just capture the state of the workflow."
    )
    
    try:
        response = litellm.completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please summarize this conversation history:\n\n{history_text}"},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[WARNING] History summarization failed: {e}")
        # Return a fallback that indicates summarization failed, 
        # or maybe we could just return the original text, but since we're compacting,
        # we can just return a generic placeholder or the raw text truncated.
        # Here we just raise it to let the caller handle it.
        raise
