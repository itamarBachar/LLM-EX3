"""
DoIt: Natural language CLI command executor.
"""

import sys
import os
import argparse
import dotenv


from doit.llm import call_llm_with_fallback
from doit.response_parser import (
    parse_llm_response,
    ResponseParseError,
    is_command_response,
    is_answer_response,
    is_not_possible_response,
    is_clarification_response,
)
from doit.safety import should_execute_command
from doit.command_executor import execute_and_display


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="doit",
        description="Convert natural language instructions to shell commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  doit "list all files in my home directory"
  doit "show me the weather"
  doit "create a backup of my Documents folder"
        """,
    )

    parser.add_argument(
        "instruction",
        nargs="?",
        help="Natural language instruction",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )

    return parser.parse_args()


def print_version() -> None:
    print("DoIt v0.1.0 - Natural language CLI command executor")


def main() -> int:
    # Load environment variables
    dotenv.load_dotenv()
    dotenv.load_dotenv(os.path.expanduser("~/.env"))

    args = parse_arguments()

    if args.version:
        print_version()
        return 0

    if not args.instruction:
        print("Error: No instruction provided.")
        print("Usage: doit \"your instruction here\"")
        return 1

    instruction = args.instruction.strip()

    if args.verbose:
        print(f"[DEBUG] Instruction: {instruction}\n")

    # print("🤔 Thinking...\n")
    llm_response = call_llm_with_fallback(instruction)

    if llm_response is None:
        print("Error: Could not get response from LLM.")
        return 1

    if args.verbose:
        print(f"[DEBUG] LLM Response:\n{llm_response}\n")

    try:
        parsed_response = parse_llm_response(llm_response)
    except ResponseParseError as e:
        print(f"Error: Could not parse LLM response: {str(e)}")
        if args.verbose:
            print(f"Raw response: {llm_response}")
        return 1

    if args.verbose:
        print(f"[DEBUG] Parsed Response Type: {parsed_response.get('type')}\n")

    if is_answer_response(parsed_response):
        print(f"💬 {parsed_response.get('answer', '')}\n")
        return 0

    if is_not_possible_response(parsed_response):
        print(f"❌ {parsed_response.get('answer', '')}\n")
        return 0

    if is_clarification_response(parsed_response):
        question = parsed_response.get("question", "")
        options = parsed_response.get("options", [])

        print(f"❓ {question}")

        for i, option in enumerate(options, start=1):
            print(f"{i}. {option}")

        print()
        return 0

    if is_command_response(parsed_response):
        command = parsed_response.get("command", "").strip()
        explanation = parsed_response.get("explanation", "")

        if args.verbose:
            print(f"[DEBUG] Command: {command}")
            print(f"[DEBUG] Explanation: {explanation}\n")

        print(command)
        print()
        print(f"💡 {explanation}\n")

        can_execute, safety_message = should_execute_command(command)

        if args.verbose:
            print(f"[DEBUG] Safety check: {safety_message}\n")

        if not can_execute:
            print(f"⛔ {safety_message}\n")
            return 1

        return execute_and_display(command)

    print(f"Error: Unexpected response type: {parsed_response.get('type')}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())