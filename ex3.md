# Assignment 3: Agents

In this assignment, we will gradually build an interactive LLM agent that executes shell commands on behalf of a user.

The agent will be structured as a command line program implemented in Python called `doit`, which takes the user request as a command-line parameter. The agent will execute `bash` or `zsh` commands. These are very common shells for Mac and Linux. They can also be installed on Windows through the WSL or the Git Bash project, but you are highly advised to transition to Mac or Linux.

---

## 1. Single Command at a Time

Write a CLI (command-line interface) program called `doit` that:
1. Takes in an instruction in natural language.
2. Translates it to a shell command in either `bash` or `zsh` (you decide which one) and prints the command.
3. Executes the command in the shell, and writes its output to the screen.

**Example usage:**
```bash
> doit "list the files in my Documents folder"

ls ~/Documents

doc1.pdf
doc2.pdf
doc3.pdf
```


### Requirements & Considerations

* The translation should be done with an LLM call using an API call to a hosted model provider.
* Despite having no file extension, `doit` should be written in Python.
* It should be added to your PATH and work when invoked from any directory in your system.
* **Questions to consider:**
* How would you capture the model’s command output? Request it in a convenient format.
* What happens if the user requests something impossible to do in the shell?
* What happens if the user asks "tell me a joke" or "what can you do"? Respond nicely.



*Note: One way to start is to separate the model’s response from the execution step. The model may need to produce a shell command, a regular answer, or an explanation.*

### Python Subprocess Example

A simple way to execute a command is with `subprocess`:

```python
import subprocess

def run_shell(command: str, shell: str = "/bin/bash"):
    result = subprocess.run(
        command,
        shell=True,
        executable=shell,
        text=True,
        capture_output=True,
        timeout=20,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }

```

*Modify or use this code as needed. Make sure to capture `stdout`, `stderr`, and the return code.*

---

## 2. Identifying Dangerous Commands

Modify the behavior of the program so that commands that modify the filesystem (create, move, delete files, etc.) are **not executed automatically**. Instead, the program should:

1. Show the command to the user.
2. Explain what it does.
3. Ask the user if they want to proceed.
4. Execute **only** if the user types `y`.

*(Think about: How will you identify these cases? One option is a separate LLM call).*

---

## 3. Model Flexibility

Extend the program to work with a local model. You must explore using all three of the following models for your experimentation and test cases:

* One LLM-provider API model
* One local instruction model **without** tool-calling support
* One local instruction model **with** tool-calling support

Use a configuration file called `doit.cfg` in your home directory to determine which model to call. Use the `LiteLLM` package to standardize calls and easily switch between models.

**Local Model Options:**

* **Medium (4B):** `qwen3:4b-instruct` (tool support) or `gemma3:4b` (general instruction).
* **Large (7B-8B):** `mistral:7b` (function calling) or `llama3:8b` (general instruction).
* **Serving Options:** Ollama (easiest), LM Studio, or llama.cpp server.

---

## 4. ACDL Documentation

Throughout the assignment, document the context sent to the LLM using [ACDL](https://acdlang26.github.io/acdlsite/syntax-reference.html).

* Do this while you work, not just at the end.
* Your report must include the ACDL descriptions of all relevant contexts and the prompt templates used.
* Include both the textual description and the generated visual representation.
* *Note: Every invocation of `doit` is considered its own turn.*

---

## 5. Multi-Turn History

Move from isolated requests to turns that depend on each other. Retain state and context between invocations.

**Example:**

```bash
> doit "list the files in my Documents folder"
> doit "now sort them by date"
> doit "no, i meant latest first"

```

*(Think about: How/where do you store history? Hidden `.doit` folder? How do you distinguish between new commands and references to old ones?)*

---

## 6. Clarifications

Add the ability for the program to ask the user when it is uncertain, and wait for an answer before continuing.

**Example:**

```bash
> doit "list the files in my home folder sorted by date"

Do you want to sort by:
1. creation date
2. access date

```

---

## 7. Richer Interactions

Allow the program to answer non-commands (e.g., "how do I do X?"). The end result should be an answer, not a shell invocation. Follow-ups like "modify it to do Y" or "execute it" should also work.

---

## 8. Memory

Allow the program to store persistent "memories" about the user. Unlike multi-turn history, memories must persist across different terminal windows, directories, and sessions.

**Example:**
`doit "move to ~/school/llms/ass3. this is my LLM class project folder."`
Later: `doit "go to my llm class project"` should navigate based on the saved memory.

---

## 9. User Awareness

Make the program aware of the user’s actions by tapping into the shell's command history (e.g., `.bash_history` or `.zsh_history`).
If a user manually runs `cd ~/school/llms/ass3` and `mkdir data`, asking `doit "summarize what I just did"` should yield a correct answer aware of the user's manual inputs.
*Changes to `.bashrc` / `.zshrc` are allowed but must be documented.*

---

## 10. Output Awareness

Make sure it is possible to ask questions directly about the shell output from the previous command.
*Example:* After `doit "list the largest files"`, the user asks `doit "which of these looks safe to delete?"`. The program should have access to the previous command's `stdout`/`stderr` to answer.

---

## 11. Multi-Tasking

Handle scenarios where a user works in multiple terminal windows simultaneously. The program must be aware of the context in which it is running, so references to history don't cross-pollinate incorrectly unless explicitly requested.

*Suggestion:* Set a session ID environment variable in your `.bashrc`/`.zshrc` to separate history streams by terminal window.

---

## 12. Further Extensions

Think of **three** additional extensions to your agent. Describe all of them in your report, and **implement one**. The implemented extension should be a real agent capability (not just a UI wrapper) that improves planning, memory, context management, or error recovery.

*Ideas:* Context compaction, multi-step tool use, project profiles, or command execution plans.

---

## 13. Grading & Submission

**What to submit:**

1. **Source Code:** Your full implementation of `doit` and any supporting files.
2. **Report:**
* Describe what you implemented for each section.
* Explain your design decisions.
* Show at least one example interaction for each feature (successful, failures, and recoveries).
* Discuss limitations and imperfections.
* Include a comparison between two local models (one with tool-calling and one without), highlighting failure cases and prompting differences.
* Include prompt templates, tool definitions, structured-output formats, or schemas used.
* Document all relevant contexts using ACDL (Text and Visuals).



**Evaluation Criteria:**

* Does the agent work completely as specified?
* Quality of "harder" agentic parts (memory, user awareness, multi-tasking).
* Clear report formatting, transparent design choices, and honest evaluation of limitations.
* Accurate and comprehensive use of ACDL documentation.

```

```