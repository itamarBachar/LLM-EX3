import os
import unittest
from pathlib import Path
from unittest.mock import patch

from doit import history_tracker, session


class TestUserAwareness(unittest.TestCase):
    def setUp(self):
        # Setup temporary directories and files
        self.test_dir = Path(__file__).parent / "scratch"
        self.test_dir.mkdir(exist_ok=True)
        self.session_dir = self.test_dir / "sessions"
        self.session_dir.mkdir(exist_ok=True)
        
        # Patch home dir or directories used by session and history_tracker
        self.sessions_patcher = patch("doit.session.Path.home", return_value=self.test_dir)
        self.tracker_home_patcher = patch("doit.history_tracker.Path.home", return_value=self.test_dir)
        self.mock_session_home = self.sessions_patcher.start()
        self.mock_tracker_home = self.tracker_home_patcher.start()

    def tearDown(self):
        self.sessions_patcher.stop()
        self.tracker_home_patcher.stop()
        
        # Clean up files inside test dir
        for p in self.test_dir.glob("**/*"):
            if p.is_file():
                p.unlink()
        for p in reversed(list(self.test_dir.glob("**/*"))):
            if p.is_dir():
                p.rmdir()
        if self.test_dir.exists():
            self.test_dir.rmdir()


    def test_session_id_detection(self):
        with patch.dict(os.environ, {"DOIT_SESSION_ID": "test_session_123"}):
            self.assertEqual(session.get_session_id(), "test_session_123")
            self.assertEqual(
                session.get_session_log_path("test_session_123"),
                self.test_dir / ".doit" / "sessions" / "test_session_123.log"
            )

    def test_bash_session_history_loading(self):
        session_id = "bash_session_xyz"
        log_file = self.test_dir / ".doit" / "sessions" / f"{session_id}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write mock manual commands (some doit, some empty, some manual)
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("mkdir data\n")
            f.write("doit \"some instruction\"\n")
            f.write("cd data\n")
            f.write("touch file.py\n")
            f.write("doit \"another instruction\"\n")
            
        with patch.dict(os.environ, {"DOIT_SESSION_ID": session_id, "SHELL": "/bin/bash"}):
            commands = history_tracker.load_recent_shell_history(limit=5)
            # Should filter out doit commands and return manual ones
            self.assertEqual(commands, ["mkdir data", "cd data", "touch file.py"])

    def test_global_history_fallback(self):
        # Mock global history file (untracked session)
        hist_file = self.test_dir / ".bash_history"
        with open(hist_file, "w", encoding="utf-8") as f:
            f.write("ls -la\n")
            f.write("#123456789\n")  # timestamp comment
            f.write("git status\n")
            
        # Ensure no session ID is active, and direct the history path mock
        with patch.dict(os.environ, {"SHELL": "/bin/bash", "DOIT_SESSION_ID": ""}):
            with patch("doit.history_tracker.get_history_file_path", return_value=hist_file):
                commands = history_tracker.load_recent_shell_history(limit=5)
                # Should skip comments
                self.assertEqual(commands, ["ls -la", "git status"])

    def test_clear_session_history(self):
        session_id = "test_clear_session"
        log_file = self.test_dir / ".doit" / "sessions" / f"{session_id}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch()
        
        self.assertTrue(log_file.exists())
        session.clear_session_history(session_id)
        self.assertFalse(log_file.exists())

    def test_tilde_expansion_in_history_path(self):
        with patch.dict(os.environ, {"HISTFILE": "~/custom_history_file"}):
            path = history_tracker.get_history_file_path("bash")
            # Should expand ~ to the home directory
            self.assertEqual(path, Path(os.path.expanduser("~/custom_history_file")))



if __name__ == "__main__":
    unittest.main()
