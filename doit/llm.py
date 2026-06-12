"""
LLM interaction module using LiteLLM for multi-provider support.

Responsibilities:
- Send natural language instructions to LLM via LiteLLM
- Request structured JSON responses
- Handle API errors gracefully
- Support multiple model providers and local models
"""

from typing import Optional
import os
import litellm
from doit.config import get_config, ConfigError, DoItConfig


SYSTEM_PROMPT = """
You are a bash command expert that converts natural language instructions into bash commands.

You must choose exactly one response type:

1. command:
Use this when the user asks for something that should be executed in bash.

2. answer:
Use this for conversational requests, greetings, jokes, help questions, or general explanations.

3. not_possible:
Use this when the request cannot reasonably be done with a standard bash command.

4. clarification:
Use this when the request is ambiguous and you need the user to choose before creating a command.

Rules:
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
            "enum": ["command", "answer", "not_possible", "clarification"],
        },
        "command": {
            "type": "string",
        },
        "explanation": {
            "type": "string",
        },
        "answer": {
            "type": "string",
        },
        "question": {
            "type": "string",
        },
        "options": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },
    },
    "required": ["type"],
    "additionalProperties": False,
}


def _get_litellm_model_id(config: DoItConfig) -> str:
    """
    Get the model ID in LiteLLM format.
    
    LiteLLM format:
    - API models: "provider/model" (e.g., "openai/gpt-4o-mini")
    - Local models: "model_name" (e.g., "mistral", "ollama/neural-chat")
    """
    provider = config.get_provider()
    model_name = config.get_model_name()
    
    if provider == "api":
        # For API models, prepend provider if not already included
        if "/" not in model_name:
            # Assume OpenAI if no provider specified
            return f"openai/{model_name}"
        return model_name
    else:
        # For local models, use as-is or with ollama prefix
        if "/" in model_name:
            return model_name
        # Default to ollama for local models
        return f"ollama/{model_name}"


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
    
    if config.is_debug():
        litellm.set_verbose(True)
    
    model_id = _get_litellm_model_id(config)
    temperature = config.get_temperature()
    max_tokens = config.get_max_tokens()
    
    try:
        # Use LiteLLM's completion endpoint
        # This works with API models and local models (via ollama)
        response = litellm.completion(
            model=model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # LiteLLM supports json_object
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
    model_id = _get_litellm_model_id(config)
    temperature = config.get_temperature()
    max_tokens = config.get_max_tokens()

    fallback_prompt = f"""
    Return only valid JSON.

    Allowed formats:

    Command:
    {{
    "type": "command",
    "command": "the bash command",
    "explanation": "brief explanation"
    }}

    Answer:
    {{
    "type": "answer",
    "answer": "your answer"
    }}

    Not possible:
    {{
    "type": "not_possible",
    "answer": "why it is not possible"
    }}

    Clarification:
    {{
    "type": "clarification",
    "question": "question for the user",
    "options": ["option 1", "option 2"]
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

    return response.choices[0].message.content.strip()


def call_llm_with_fallback(
    instruction: str,
    max_retries: int = 2,
) -> Optional[str]:
    """
    Attempt structured output first.
    If it fails, use prompt-based JSON fallback.
    
    Supports multiple model providers via configuration.
    """
    config = get_config()
    effective_retries = max_retries or config.get_max_retries()
    
    for attempt in range(effective_retries):
        try:
            return call_llm_for_bash(instruction)

        except Exception as e:
            if attempt < effective_retries - 1:
                print(f"[WARNING] Error (attempt {attempt + 1}): {str(e)}")
                continue

            print("[WARNING] Structured output failed. Trying prompt-based JSON fallback.")

            try:
                return call_llm_for_bash_prompt_fallback(instruction)
            except Exception as fallback_error:
                print(f"[ERROR] Fallback failed: {str(fallback_error)}")
                return None

        except ConfigError as e:
            print(f"[ERROR] Configuration error: {str(e)}")
            return None

    return None