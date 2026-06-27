"""
DoIt: Natural language CLI command executor.
"""

import sys
import os
import argparse
from typing import Optional

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
from doit import history, memory
from doit.config import get_config, ConfigError
from doit.session import get_session_id, clear_session_history


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

    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Ignore and do not record multi-turn history for this invocation",
    )

    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear the conversation history for the current session and exit",
    )

    parser.add_argument(
        "--clear-memories",
        action="store_true",
        help="Clear all persistent memories and exit",
    )

    parser.add_argument(
        "--show-memories",
        action="store_true",
        help="Show all saved persistent memories and exit",
    )

    return parser.parse_args()


def print_version() -> None:
    print("DoIt v0.1.0 - Natural language CLI command executor")


def _history_enabled(args: argparse.Namespace) -> bool:
    """Decide whether to use/record history for this invocation."""
    if args.no_history:
        return False
    try:
        return get_config().is_history_enabled()
    except ConfigError:
        # If config can't be read, fall back to enabling history by default.
        return True


def _history_limit() -> int:
    """Resolve how many recent turns to include as context."""
    try:
        return get_config().get_history_compaction_threshold()
    except ConfigError:
        return 10


# Cap on how many times we will re-ask the user before giving up, to avoid the
# model getting stuck in a clarification loop.
MAX_CLARIFICATION_ROUNDS = 3


def prompt_for_clarification(question: str, options: list) -> Optional[str]:
    """
    Show a clarification question (and any options) and wait for the user.

    Returns the user's answer as a string. If options are shown and the user
    types a valid option number, the corresponding option text is returned;
    otherwise the raw typed text is used. Returns None when there is no
    interactive terminal or the user aborts, so the caller can stop cleanly.
    """
    print(f"❓ {question}")
    for i, option in enumerate(options, start=1):
        print(f"  {i}. {option}")
    print()

    if not sys.stdin.isatty():
        print("Non-interactive terminal detected; cannot ask for clarification.")
        return None

    prompt = "Your answer (type a number or describe): " if options else "Your answer: "

    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nClarification cancelled.")
        return None

    if not raw:
        return None

    # If the user picked a valid option number, map it to the option text.
    if options and raw.isdigit():
        index = int(raw) - 1
        if 0 <= index < len(options):
            return options[index]

    return raw


def build_clarified_instruction(original: str, exchanges: list) -> str:
    """
    Combine the original request with the clarification Q&A into a single
    instruction for the next model call, so every backend receives the same
    disambiguated context.
    """
    lines = [f"Original request: {original}", ""]
    for question, answer in exchanges:
        lines.append(f"You asked the user: {question}")
        lines.append(f"The user answered: {answer}")
    lines.append("")
    lines.append(
        "Using the clarification(s) above, fulfill the original request now. "
        "Do not ask again unless it is still genuinely impossible to proceed."
    )
    return "\n".join(lines)


def process_response_memories(parsed_response: dict, verbose: bool = False) -> None:
    """Extract and apply any memory updates returned by the LLM."""
    try:
        if not get_config().is_memory_enabled():
            return
    except Exception:
        pass

    new_memories = parsed_response.get("new_memories") or []
    forget_memories = parsed_response.get("forget_memories") or []
    
    if new_memories or forget_memories:
        memory.update_memories(new_memories, forget_memories)
        if verbose:
            if new_memories:
                print(f"[DEBUG] Memory added: {new_memories}")
            if forget_memories:
                print(f"[DEBUG] Memory forgotten: {forget_memories}")


def main() -> int:
    # Load environment variables
    dotenv.load_dotenv()
    dotenv.load_dotenv(os.path.expanduser("~/.env"))

    args = parse_arguments()

    if args.version:
        print_version()
        return 0

    if args.clear_history:
        cleared = history.clear_history()
        
        # Clear session history if we have a session ID
        session_id = get_session_id()
        if session_id:
            if clear_session_history(session_id):
                    cleared = True

        if cleared:
            print("🧹 Cleared conversation history.")
        else:
            print("No conversation history to clear.")
        return 0

    if args.clear_memories:
        cleared = memory.clear_memories()
        if cleared:
            print("🧹 Cleared all persistent memories.")
        else:
            print("No persistent memories to clear.")
        return 0

    if args.show_memories:
        memories = memory.load_memories()
        if memories:
            print("🧠 Saved persistent memories:")
            for m in memories:
                print(f"  - {m}")
        else:
            print("No persistent memories saved yet.")
        return 0

    if not args.instruction:
        print("Error: No instruction provided.")
        print("Usage: doit \"your instruction here\"")
        return 1

    instruction = args.instruction.strip()

    if args.verbose:
        print(f"[DEBUG] Instruction: {instruction}\n")

    # Determine whether multi-turn history should be used this invocation.
    history_enabled = _history_enabled(args)

    history_context = None
    if history_enabled:
        recent_turns = history.load_recent_turns(_history_limit())
        history_context = history.format_history_for_prompt(recent_turns) or None
        if args.verbose and history_context:
            print(f"[DEBUG] Loaded {len(recent_turns)} prior turn(s) as context.\n")

    # Load memory context if enabled.
    memory_context = None
    try:
        if get_config().is_memory_enabled():
            memories = memory.load_memories()
            memory_context = memory.format_memories_for_prompt(memories) or None
            if args.verbose and memory_context:
                print(f"[DEBUG] Loaded {len(memories)} persistent memories.\n")
    except Exception as e:
        if args.verbose:
            print(f"[DEBUG] Failed to load memory context: {e}")

    def record(response_type: str, **kwargs) -> None:
        """Record this turn to history when history is enabled."""
        if history_enabled:
            history.append_turn(instruction, response_type, **kwargs)

    # The model may respond with a clarification question instead of a final
    # answer. When it does, we ask the user, then re-query with the original
    # request plus the clarification exchange, looping up to a small cap.
    model_input = instruction
    clarification_exchanges = []

    for clarification_round in range(MAX_CLARIFICATION_ROUNDS + 1):
        # print("🤔 Thinking...\n")
        llm_response = call_llm_with_fallback(
            model_input,
            history_context=history_context,
            memory_context=memory_context,
        )

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

        if not is_clarification_response(parsed_response):
            break

        # Clarification requested.
        question = parsed_response.get("question", "")
        options = parsed_response.get("options", [])

        if clarification_round >= MAX_CLARIFICATION_ROUNDS:
            print(f"❓ {question}")
            print("\nToo many clarification rounds; stopping. Please rephrase "
                  "your request with more detail.\n")
            record("clarification", answer=question)
            return 1

        answer = prompt_for_clarification(question, options)

        if answer is None:
            # No interactive terminal, or the user aborted.
            record("clarification", answer=question)
            return 1

        clarification_exchanges.append((question, answer))
        model_input = build_clarified_instruction(instruction, clarification_exchanges)

    # Process memories for the final response
    process_response_memories(parsed_response, args.verbose)

    if is_answer_response(parsed_response):
        answer = parsed_response.get("answer", "")
        print(f"💬 {answer}\n")
        record("answer", answer=answer)
        return 0

    if is_not_possible_response(parsed_response):
        answer = parsed_response.get("answer", "")
        print(f"❌ {answer}\n")
        record("not_possible", answer=answer)
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
            # Still record the proposed command so a follow-up can reference it.
            record("command", command=command, explanation=explanation)
            return 1

        returncode = execute_and_display(command)
        record("command", command=command, explanation=explanation)
        return returncode

    print(f"Error: Unexpected response type: {parsed_response.get('type')}\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())