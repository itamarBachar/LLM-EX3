import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from doit import history


class TestOutputAwarenessHistory(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for testing history files
        self.test_dir = Path(__file__).parent / "scratch"
        self.test_dir.mkdir(exist_ok=True)
        
        # Patch get_history_dir to point to our test directory
        self.get_history_dir_patcher = patch("doit.history.get_history_dir", return_value=self.test_dir)
        self.mock_get_history_dir = self.get_history_dir_patcher.start()

        # Patch environment to clear DOIT_SESSION_ID by default for predictable global history
        self.env_patcher = patch.dict(os.environ)
        self.env_patcher.start()
        if "DOIT_SESSION_ID" in os.environ:
            del os.environ["DOIT_SESSION_ID"]

        # Clean up files inside test dir
        self._cleanup_test_dir()

    def tearDown(self):
        self.env_patcher.stop()
        self.get_history_dir_patcher.stop()
        self._cleanup_test_dir()
        if self.test_dir.exists():
            try:
                self.test_dir.rmdir()
            except OSError:
                pass

    def _cleanup_test_dir(self):
        if self.test_dir.exists():
            # Delete recursively
            for p in sorted(self.test_dir.glob("**/*"), reverse=True):
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()

    def test_truncate_output(self):
        # Short string remains unchanged
        self.assertEqual(history._truncate_output("hello"), "hello")
        self.assertEqual(history._truncate_output(""), "")

        # Long string gets truncated
        long_str = "A" * 3000
        truncated = history._truncate_output(long_str, max_chars=10)
        self.assertIn("... [TRUNCATED] ...", truncated)
        self.assertEqual(truncated, "AAAAA\n... [TRUNCATED] ...\nAAAAA")

    def test_history_file_resolution(self):
        # No session ID should return global history file path
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(history._history_file(), self.test_dir / "history.jsonl")

        # Session ID set should return session-specific path under sessions/
        with patch.dict(os.environ, {"DOIT_SESSION_ID": "session_123"}):
            self.assertEqual(history._history_file(), self.test_dir / "sessions" / "history_session_123.jsonl")

    def test_append_turn_with_outputs(self):
        # Append turn without output fields (defaults should be handled)
        history.append_turn("list files", "command", command="ls")
        
        # Read the file and verify structure
        history_path = self.test_dir / "history.jsonl"
        self.assertTrue(history_path.exists())
        
        with open(history_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data["instruction"], "list files")
        self.assertEqual(data["command"], "ls")
        self.assertEqual(data["stdout"], "")
        self.assertEqual(data["stderr"], "")
        self.assertIsNone(data["returncode"])

        # Append turn with output fields
        history.append_turn(
            "list files again",
            "command",
            command="ls",
            stdout="file1.txt\nfile2.txt",
            stderr="warning: folder is huge",
            returncode=0,
        )

        with open(history_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 2)
        data2 = json.loads(lines[1])
        self.assertEqual(data2["instruction"], "list files again")
        self.assertEqual(data2["stdout"], "file1.txt\nfile2.txt")
        self.assertEqual(data2["stderr"], "warning: folder is huge")
        self.assertEqual(data2["returncode"], 0)

    def test_session_isolation(self):
        # Write to session 1
        with patch.dict(os.environ, {"DOIT_SESSION_ID": "session_A"}):
            history.append_turn("instruction A", "answer", answer="res A")
            turns_A = history.load_recent_turns()
            self.assertEqual(len(turns_A), 1)
            self.assertEqual(turns_A[0]["instruction"], "instruction A")

        # Write to session 2
        with patch.dict(os.environ, {"DOIT_SESSION_ID": "session_B"}):
            history.append_turn("instruction B", "answer", answer="res B")
            turns_B = history.load_recent_turns()
            self.assertEqual(len(turns_B), 1)
            self.assertEqual(turns_B[0]["instruction"], "instruction B")

        # Ensure session A was not modified
        with patch.dict(os.environ, {"DOIT_SESSION_ID": "session_A"}):
            turns_A = history.load_recent_turns()
            self.assertEqual(len(turns_A), 1)
            self.assertEqual(turns_A[0]["instruction"], "instruction A")


if __name__ == "__main__":
    unittest.main()
