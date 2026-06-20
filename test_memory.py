import os
import unittest
from pathlib import Path
from unittest.mock import patch

from doit import memory


class TestDoItMemory(unittest.TestCase):
    def setUp(self):
        # Use a temporary memory file path for testing
        self.test_dir = Path(__file__).parent / "scratch"
        self.test_dir.mkdir(exist_ok=True)
        self.test_file = self.test_dir / "test_memories.json"
        
        # Patch get_memory_file to return our test file
        self.get_memory_file_patcher = patch("doit.memory.get_memory_file", return_value=self.test_file)
        self.mock_get_memory_file = self.get_memory_file_patcher.start()

        # Clean up files before test
        if self.test_file.exists():
            self.test_file.unlink()

    def tearDown(self):
        self.get_memory_file_patcher.stop()
        if self.test_file.exists():
            self.test_file.unlink()
        if self.test_dir.exists():
            try:
                self.test_dir.rmdir()
            except OSError:
                pass

    def test_load_empty_memories(self):
        memories = memory.load_memories()
        self.assertEqual(memories, [])

    def test_add_memories(self):
        memory.update_memories(["The user's project folder is ~/school/llms/ass3."], [])
        memories = memory.load_memories()
        self.assertEqual(memories, ["The user's project folder is ~/school/llms/ass3."])

    def test_avoid_duplicates(self):
        memory.update_memories(["The user's project folder is ~/school/llms/ass3."], [])
        memory.update_memories(["The user's project folder is ~/school/llms/ass3."], [])
        memories = memory.load_memories()
        self.assertEqual(memories, ["The user's project folder is ~/school/llms/ass3."])

        # Case-insensitive duplicate check
        memory.update_memories(["the user's project folder is ~/school/llms/ass3"], [])
        memories = memory.load_memories()
        self.assertEqual(memories, ["The user's project folder is ~/school/llms/ass3."])

    def test_forget_memories(self):
        memory.update_memories(
            ["The user's project folder is ~/school/llms/ass3.", "The user prefers python3."],
            []
        )
        
        # Forget one memory
        memory.update_memories([], ["The user prefers python3."])
        memories = memory.load_memories()
        self.assertEqual(memories, ["The user's project folder is ~/school/llms/ass3."])

    def test_update_contradicting_memory(self):
        memory.update_memories(["The user's project folder is ~/school/llms/ass3."], [])
        
        # LLM reports a change: add new memory and forget the old one
        memory.update_memories(
            ["The user's project folder is ~/school/llms/ass4."],
            ["The user's project folder is ~/school/llms/ass3."]
        )
        memories = memory.load_memories()
        self.assertEqual(memories, ["The user's project folder is ~/school/llms/ass4."])

    def test_clear_memories(self):
        memory.update_memories(["Some memory."], [])
        self.assertTrue(self.test_file.exists())
        
        cleared = memory.clear_memories()
        self.assertTrue(cleared)
        self.assertFalse(self.test_file.exists())


if __name__ == "__main__":
    unittest.main()
