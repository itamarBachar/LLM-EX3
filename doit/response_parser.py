"""
Response parser module for handling LLM output.

Responsibilities:
- Parse JSON responses from LLM
- Validate response schema
- Handle malformed JSON gracefully
- Extract typed responses
"""

import json
import re
from typing import Dict, Any


class ResponseParseError(Exception):
    """Raised when LLM response cannot be parsed."""
    pass


def extract_json_from_response(raw_response: str) -> Dict[str, Any]:
    """
    Extract valid JSON from LLM response.
    """
    markdown_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    markdown_match = re.search(markdown_pattern, raw_response)

    if markdown_match:
        json_text = markdown_match.group(1).strip()
    else:
        json_text = raw_response.strip()

    try:
        parsed = json.loads(json_text)
        return parsed
    except json.JSONDecodeError as e:
        raise ResponseParseError(
            f"Invalid JSON in response: {str(e)}\nRaw: {json_text[:200]}"
        )


def validate_response_schema(response: Dict[str, Any]) -> bool:
    """
    Validate that response matches one of the expected schemas.
    """
    if not isinstance(response, dict):
        raise ResponseParseError(f"Response must be an object, got {type(response)}")
    # Attempt to repair common LLM errors
    if "type" not in response:
        if "command" in response:
            response["type"] = "command"
        elif "response_type" in response:
            response["type"] = response.pop("response_type")

    response_type = response.get("type")

    if not response_type:
        raise ResponseParseError(
            f"Response missing 'type' field. Got: {response.keys()}"
        )

    if response_type not in ["command", "answer", "not_possible", "clarification"]:
        raise ResponseParseError(
            f"Unknown response type: '{response_type}'. Expected: command, answer, not_possible, or clarification"
        )

    if response_type == "command":
        required_keys = {"type", "command", "explanation"}

        if "explanation" not in response or response["explanation"] is None:
            response["explanation"] = "No explanation provided."

        if not required_keys.issubset(response.keys()):
            raise ResponseParseError(
                f"Command response missing keys. Required: {required_keys}, Got: {response.keys()}"
            )

        if not isinstance(response["command"], str) or not response["command"].strip():
            raise ResponseParseError("Command must be a non-empty string")

        if not isinstance(response["explanation"], str):
            raise ResponseParseError("Explanation must be a string")

        return True

    elif response_type == "answer":
        required_keys = {"type", "answer"}

        if not required_keys.issubset(response.keys()):
            if "answer" not in response:
                response["answer"] = "No answer provided."
            
            if not required_keys.issubset(response.keys()):
                raise ResponseParseError(
                    f"Answer response missing keys. Required: {required_keys}, Got: {response.keys()}"
                )

        if not isinstance(response["answer"], str):
            raise ResponseParseError("Answer must be a string")

        return True

    elif response_type == "not_possible":
        required_keys = {"type", "explanation"}

        if "explanation" not in response or response["explanation"] is None:
            response["explanation"] = "The model indicated this was not possible but provided no reason."

        if not required_keys.issubset(response.keys()):
            raise ResponseParseError(
                f"not_possible response missing keys. Required: {required_keys}, Got: {response.keys()}"
            )

        if not isinstance(response["explanation"], str):
            raise ResponseParseError("Explanation must be a string")

        return True

    elif response_type == "clarification":
        required_keys = {"type", "question"}

        if not required_keys.issubset(response.keys()):
            raise ResponseParseError(
                f"Clarification response missing keys. Required: {required_keys}, Got: {response.keys()}"
            )

        if not isinstance(response["question"], str):
            raise ResponseParseError("Question must be a string")

        return True

    return False


def parse_llm_response(raw_response: str) -> Dict[str, Any]:
    """
    Parse and validate LLM response.
    """
    try:
        parsed = extract_json_from_response(raw_response)
        validate_response_schema(parsed)
        
        # Map 2-type schema explanation to answer for backward compatibility
        if parsed.get("type") == "not_possible":
            parsed["answer"] = parsed.get("explanation", "")
        
        # Clean up null/None values from strict schema response
        if parsed.get("command") is None:
            parsed["command"] = ""
        if parsed.get("explanation") is None:
            parsed["explanation"] = ""
        if parsed.get("answer") is None:
            parsed["answer"] = ""
        if parsed.get("question") is None:
            parsed["question"] = ""
        if parsed.get("options") is None:
            parsed["options"] = []
            
        return parsed
    except ResponseParseError:
        raise
    except Exception as e:
        raise ResponseParseError(f"Unexpected error parsing response: {str(e)}")


def is_command_response(response: Dict[str, Any]) -> bool:
    return response.get("type") == "command"


def is_answer_response(response: Dict[str, Any]) -> bool:
    return response.get("type") == "answer"


def is_not_possible_response(response: Dict[str, Any]) -> bool:
    return response.get("type") == "not_possible"


def is_clarification_response(response: Dict[str, Any]) -> bool:
    return response.get("type") == "clarification"