# DoIt Manual Test Scenarios

This file contains 10 test scenarios, each consisting of exactly 15 sequential commands. Use these scenarios to verify the functionality of `doit` under different conditions (history, memory, safety, non-commands, pipelines, etc.).

---

## Test Scenario 1: Navigation & Memory Updates (Focus on Memory & cd)
1. `doit --clear-memories`
2. `doit --clear-history`
3. `doit "move to ~/school/llms/ass3. this is my LLM class project folder."`
4. `doit --show-memories`
5. `doit "go to my llm class project"`
6. `doit "where am I right now?"`
7. `doit "create a new folder here called data"`
8. `doit "now rename the data folder to datasets"`
9. `doit "my LLM class project folder is now ~/school/llms/ass4"`
10. `doit --show-memories`
11. `doit "go to my llm class project"`
12. `doit "tell me a joke about computer science"`
13. `doit "create a file here called notes.txt"`
14. `doit "add the text 'study hard' to notes.txt"`
15. `doit "show the contents of notes.txt"`

---

## Test Scenario 2: Multi-Turn Conversation & History Context
1. `doit --clear-history`
2. `doit "list files in the current directory"`
3. `doit "now sort them by size"`
4. `doit "no, i meant latest modified first"`
5. `doit "show only the top 3 files"`
6. `doit "how do I make the first file executable?"`
7. `doit "show the permissions of that file"`
8. `doit "make it executable"`
9. `doit "run it"`
10. `doit "what does chmod +x do?"`
11. `doit "list only directories here"`
12. `doit "now sort them alphabetically"`
13. `doit "now reverse the sort"`
14. `doit "explain what we just did"`
15. `doit "clear the history"`

---

## Test Scenario 3: Safety Checks & Filesystem Modifications
1. `doit "create a file named dangerous.sh"`
2. `doit "write 'echo hello' into dangerous.sh"`
3. `doit "chmod 777 dangerous.sh"`
4. `doit "run dangerous.sh"`
5. `doit "remove dangerous.sh"`
6. `doit "mkdir -p test_safety/subdir"`
7. `doit "create a dummy file in test_safety/subdir/dummy.log"`
8. `doit "delete test_safety folder and all its contents"`
9. `doit "what happens if I run rm -rf /?"`
10. `doit "reboot the system"`
11. `doit "change the permissions of the current directory to 777"`
12. `doit "move all .txt files to a backup directory"`
13. `doit "remove the backup directory"`
14. `doit "kill a process named sleep"`
15. `doit "show disk usage in human readable format"`

---

## Test Scenario 4: Clarification Loop & Rephrasing
1. `doit --clear-history`
2. `doit "sort files"`
3. `doit "by extension"`
4. `doit "show the command to do that"`
5. `doit "run it"`
6. `doit "find files"`
7. `doit "named test"`
8. `doit "in my home directory"`
9. `doit "show only the counts"`
10. `doit "explain what the options used mean"`
11. `doit "search for patterns"`
12. `doit "pattern is 'import'"`
13. `doit "in all python files"`
14. `doit "case insensitive"`
15. `doit "count the lines matching it"`

---

## Test Scenario 5: Richer Interactions & Non-Commands
1. `doit "what is the difference between bash and zsh?"`
2. `doit "how do I find my IP address in the terminal?"`
3. `doit "explain what grep stands for"`
4. `doit "how does public key cryptography work?"`
5. `doit "give me an example of using the find command"`
6. `doit "now show me how to do it with locate instead"`
7. `doit "what does the output of df -h mean?"`
8. `doit "tell me what lsof is used for"`
9. `doit "how do I kill port 8080?"`
10. `doit "show me the command for that"`
11. `doit "execute it"`
12. `doit "what are environment variables?"`
13. `doit "how do I set one temporarily?"`
14. `doit "and how do I set one permanently?"`
15. `doit "list all system users"`

---

## Test Scenario 6: Memory for User Preferences & Configurations
1. `doit --clear-memories`
2. `doit "I prefer using python3 over python. remember this."`
3. `doit --show-memories`
4. `doit "create a simple hello world script"`
5. `doit "how do I run it?"`
6. `doit "run it"`
7. `doit "I also prefer zsh over bash"`
8. `doit --show-memories`
9. `doit "write a loop that prints numbers 1 to 5"`
10. `doit "my preferred python version is zsh? no, zsh is my preferred shell."`
11. `doit "my preferred python command has changed to python3.11"`
12. `doit --show-memories`
13. `doit "show me how to run a python script"`
14. `doit "explain the differences in zsh vs bash loops"`
15. `doit --clear-memories`

---

## Test Scenario 7: Output Awareness & Diagnostics
1. `doit "echo -e 'Line 1: Error occurred\nLine 2: Warning\nLine 3: Success' > test_log.txt"`
2. `doit "cat test_log.txt"`
3. `doit "which of those lines had an error?"`
4. `doit "grep for 'Warning' in it"`
5. `doit "what is the size of test_log.txt?"`
6. `doit "ls -l test_log.txt"`
7. `doit "who is the owner of this file?"`
8. `doit "change the owner to nobody"`
9. `doit "no, keep it as the current owner"`
10. `doit "compress test_log.txt to test_log.tar.gz"`
11. `doit "extract the compressed file"`
12. `doit "compare the extracted file with the original"`
13. `doit "show diff between them"`
14. `doit "clean up all test_log files"`
15. `doit "are they deleted?"`

---

## Test Scenario 8: Complex Shell Pipelines and Tools
1. `doit "find all python files in the current folder and search for 'importos'"`
2. `doit "no, i meant search for 'import os' with space"`
3. `doit "show only filenames matching it"`
4. `doit "now count how many such files exist"`
5. `doit "list the 5 largest files in /var/log"`
6. `doit "explain what du -sh * does"`
7. `doit "run du -sh * in the current folder"`
8. `doit "sort the output of that command numerically"`
9. `doit "show only the top 10 items"`
10. `doit "what is the biggest subdirectory?"`
11. `doit "check if git is installed"`
12. `doit "show the git version"`
13. `doit "show git status"`
14. `doit "show git remote configuration"`
15. `doit "explain git commit vs push"`

---

## Test Scenario 9: System Info, Processes & Monitoring
1. `doit "show current date and time"`
2. `doit "show calendar for this month"`
3. `doit "how long has the system been running?"`
4. `doit "who is logged in?"`
5. `doit "show the CPU architecture"`
6. `doit "show available memory in megabytes"`
7. `doit "show disk usage stats"`
8. `doit "list all running processes"`
9. `doit "filter them to show only python processes"`
10. `doit "which python process is using the most CPU?"`
11. `doit "start a sleep process in background for 100 seconds"`
12. `doit "find the PID of that sleep process"`
13. `doit "kill that process"`
14. `doit "verify it is terminated"`
15. `doit "show network connections"`

---

## Test Scenario 10: Multi-Tasking & Environment Handling
1. `doit --clear-history`
2. `doit "export MY_VAR='LLM_EX3'"`
3. `doit "print the value of MY_VAR"`
4. `doit "how do I verify if a port is in use?"`
5. `doit "check if port 22 is open"`
6. `doit "list active network interfaces"`
7. `doit "show the routing table"`
8. `doit "what is my local hostname?"`
9. `doit "check if google.com is reachable"`
10. `doit "ping it 3 times"`
11. `doit "show the contents of /etc/hosts"`
12. `doit "explain the purpose of DNS"`
13. `doit "lookup the IP address of github.com"`
14. `doit "find all files modified in the last 24 hours"`
15. `doit "summarize what we did in this session"`
