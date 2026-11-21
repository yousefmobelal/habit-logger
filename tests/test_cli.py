"""End-to-end tests for the command-line entry point."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")

SUMMARY_ZERO = (
    "Total tasks: 0\n"
    "Pending tasks: 0\n"
    "Completed tasks: 0\n"
    "Total habits: 0\n"
    "Habits logged today: 0\n"
)


class CliTestCase(unittest.TestCase):
    """Run the real CLI against a temporary database for every test."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = os.path.join(self.temp_dir.name, "db.json")
        self.env = os.environ.copy()
        self.env["HABIT_LOGGER_DB"] = self.db_path

    def run_cli(self, *args):
        """Run ``main.py`` in a fresh process with the temporary database."""
        return subprocess.run(
            [sys.executable, MAIN_PY, *args],
            cwd=PROJECT_ROOT,
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def assert_no_traceback(self, result):
        self.assertNotIn("Traceback", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def assert_result(self, result, code, stdout="", stderr=""):
        """Assert the exact process outcome and absence of a traceback."""
        self.assertEqual(result.returncode, code, result.stderr)
        self.assertEqual(result.stdout, stdout)
        self.assertEqual(result.stderr, stderr)
        self.assert_no_traceback(result)

    def assert_success(self, stdout, *args):
        """Run *args* expecting exit 0, exact stdout and empty stderr."""
        self.assert_result(self.run_cli(*args), 0, stdout=stdout)

    def assert_failure(self, stderr, *args):
        """Run *args* expecting exit 1, exact stderr and empty stdout."""
        self.assert_result(self.run_cli(*args), 1, stderr=stderr)

    def read_bytes(self):
        with open(self.db_path, "rb") as handle:
            return handle.read()

    def read_db(self):
        with open(self.db_path, "r", encoding="utf-8") as handle:
            return json.load(handle)


class HelpAndEntryPointTests(CliTestCase):
    def test_root_help_lists_all_top_level_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assert_no_traceback(result)
        self.assertTrue(result.stdout.startswith("usage: main.py "))
        lines = result.stdout.splitlines()
        for name, help_text in (
            ("task", "Manage one-time tasks."),
            ("habit", "Manage daily habits."),
            ("summary", "Show task and habit counts."),
        ):
            self.assertTrue(
                any(
                    line.startswith(f"    {name}") and line.endswith(help_text)
                    for line in lines
                ),
                f"missing help line for {name}: {result.stdout}",
            )
        self.assertFalse(os.path.exists(self.db_path))

    def test_task_help_lists_all_task_actions(self):
        result = self.run_cli("task", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assert_no_traceback(result)
        self.assertIn("  {add,list,complete,uncomplete,delete}", result.stdout)
        for help_text in (
            "Add a new task.",
            "List all tasks.",
            "Mark a task complete.",
            "Mark a task pending.",
            "Delete a task.",
        ):
            self.assertIn(help_text, result.stdout)
        self.assertFalse(os.path.exists(self.db_path))

    def test_habit_help_lists_all_habit_actions(self):
        result = self.run_cli("habit", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assert_no_traceback(result)
        self.assertIn("  {add,list,log,delete}", result.stdout)
        for help_text in (
            "Add a new habit.",
            "List all habits.",
            "Log a habit for today.",
            "Delete a habit.",
        ):
            self.assertIn(help_text, result.stdout)
        self.assertFalse(os.path.exists(self.db_path))

    def test_no_arguments_exits_zero_without_output(self):
        self.assert_result(self.run_cli(), 0)
        self.assertFalse(os.path.exists(self.db_path))

    def test_missing_action_argument_is_a_usage_error(self):
        result = self.run_cli("task", "complete")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(
            result.stderr.endswith(
                "main.py task complete: error: "
                "the following arguments are required: task_id\n"
            )
        )
        self.assert_no_traceback(result)

    def test_unknown_command_is_a_usage_error(self):
        result = self.run_cli("bogus")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.startswith("usage: main.py "))
        self.assertTrue(result.stderr.endswith(")\n"))
        self.assertIn(
            "main.py: error: argument command: invalid choice: 'bogus' "
            "(choose from ",
            result.stderr,
        )
        for name in ("task", "habit", "summary"):
            self.assertIn(name, result.stderr)
        self.assert_no_traceback(result)


class EmptyDatabaseTests(CliTestCase):
    def test_task_list_prints_empty_message_without_creating_db(self):
        self.assert_success("No tasks yet.\n", "task", "list")
        self.assertFalse(os.path.exists(self.db_path))

    def test_habit_list_prints_empty_message_without_creating_db(self):
        self.assert_success("No habits yet.\n", "habit", "list")
        self.assertFalse(os.path.exists(self.db_path))

    def test_summary_prints_zero_counts_without_creating_db(self):
        self.assert_success(SUMMARY_ZERO, "summary")
        self.assertFalse(os.path.exists(self.db_path))


class CrossInvocationTests(CliTestCase):
    def test_state_persists_across_separate_invocations(self):
        today = date.today().isoformat()
        self.assert_success("Added task 1: Study\n", "task", "add", "Study")
        self.assert_success("Completed task 1: Study\n", "task", "complete", "1")
        self.assert_success("1: Study [completed]\n", "task", "list")
        self.assert_success(
            "Uncompleted task 1: Study\n", "task", "uncomplete", "1"
        )
        self.assert_success("Completed task 1: Study\n", "task", "complete", "1")
        self.assert_success("Added habit 1: Read\n", "habit", "add", "Read")
        self.assert_success(
            f"Logged habit 1: Read on {today}\n", "habit", "log", "1"
        )
        self.assert_success("1: Study [completed]\n", "task", "list")
        self.assert_success("1: Read\n", "habit", "list")
        self.assert_success(
            "Total tasks: 1\n"
            "Pending tasks: 0\n"
            "Completed tasks: 1\n"
            "Total habits: 1\n"
            "Habits logged today: 1\n",
            "summary",
        )
        db = self.read_db()
        self.assertEqual(db["tasks"][0]["id"], 1)
        self.assertEqual(db["habits"][0]["logs"], [today])

    def test_deleted_task_id_is_not_reused(self):
        self.assert_success("Added task 1: Write tests\n", "task", "add", "Write tests")
        self.assert_success(
            "Deleted task 1: Write tests\n", "task", "delete", "1"
        )
        self.assert_success(
            "Added task 2: Write more tests\n",
            "task",
            "add",
            "Write more tests",
        )
        self.assert_success("2: Write more tests [pending]\n", "task", "list")
        self.assertEqual(self.read_db()["next_task_id"], 3)

    def test_deleted_habit_id_is_not_reused(self):
        self.assert_success("Added habit 1: Read\n", "habit", "add", "Read")
        self.assert_success("Deleted habit 1: Read\n", "habit", "delete", "1")
        self.assert_success("Added habit 2: Meditate\n", "habit", "add", "Meditate")
        self.assert_success("2: Meditate\n", "habit", "list")
        self.assertEqual(self.read_db()["next_habit_id"], 3)

    def test_task_and_habit_ids_are_independent(self):
        self.assert_success("Added task 1: T\n", "task", "add", "T")
        self.assert_success("Added habit 1: H\n", "habit", "add", "H")
        self.assert_success("1: T [pending]\n", "task", "list")
        self.assert_success("1: H\n", "habit", "list")
        db = self.read_db()
        self.assertEqual(db["next_task_id"], 2)
        self.assertEqual(db["next_habit_id"], 2)

    def test_second_log_on_the_same_day_is_rejected_without_writing(self):
        today = date.today().isoformat()
        self.assert_success("Added habit 1: Read\n", "habit", "add", "Read")
        self.assert_success(
            f"Logged habit 1: Read on {today}\n", "habit", "log", "1"
        )
        before = self.read_bytes()
        self.assert_failure(
            f"Habit 'Read' is already logged on {today}.\n",
            "habit",
            "log",
            "1",
        )
        self.assertEqual(self.read_bytes(), before)


class InvalidInputTests(CliTestCase):
    def test_non_numeric_task_id_is_reported(self):
        self.assert_failure(
            "invalid literal for int() with base 10: 'abc'\n",
            "task",
            "complete",
            "abc",
        )
        self.assertFalse(os.path.exists(self.db_path))

    def test_empty_and_blank_names_are_rejected_without_writing(self):
        self.assert_failure(
            "Task name must be a non-empty string.\n", "task", "add", ""
        )
        self.assert_failure(
            "Habit name must be a non-empty string.\n", "habit", "add", "   "
        )
        self.assertFalse(os.path.exists(self.db_path))

    def test_invalid_and_unknown_ids_leave_database_unchanged(self):
        self.assert_success("Added task 1: Seed\n", "task", "add", "Seed")
        self.assert_success("Added habit 1: Seed\n", "habit", "add", "Seed")
        before = self.read_bytes()

        cases = (
            ("Task id must be a positive integer, got 0.\n", "task", "complete", "0"),
            ("No task found with id 999.\n", "task", "delete", "999"),
            (
                "invalid literal for int() with base 10: 'abc'\n",
                "habit",
                "log",
                "abc",
            ),
            ("No habit found with id 999.\n", "habit", "delete", "999"),
        )
        for expected_stderr, *args in cases:
            with self.subTest(args=args):
                self.assert_failure(expected_stderr, *args)
                self.assertEqual(self.read_bytes(), before)

    def test_corrupt_json_is_reported_and_never_overwritten(self):
        content = "{not json"
        with open(self.db_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        before = self.read_bytes()
        with self.assertRaises(json.JSONDecodeError) as caught:
            json.loads(content)
        expected = f"Invalid JSON in {self.db_path}: {caught.exception}\n"

        self.assert_failure(expected, "task", "list")
        self.assertEqual(self.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
