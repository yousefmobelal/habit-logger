"""Tests for the task CLI commands."""

import argparse
import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from commands import task
from main import main
from storage import json_storage

EMPTY_DB = {
    "tasks": [],
    "habits": [],
    "next_task_id": 1,
    "next_habit_id": 1,
}


def populated_db():
    """Return a small database with one pending and one completed task."""
    return {
        "tasks": [
            {"id": 1, "name": "Study", "completed": False},
            {"id": 2, "name": "Exercise", "completed": True},
        ],
        "habits": [],
        "next_task_id": 3,
        "next_habit_id": 1,
    }


class TaskCommandTestCase(unittest.TestCase):
    """Shared parser, temporary database, and output helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "db.json")
        self.original_env = os.environ.get("HABIT_LOGGER_DB")
        self.original_db_path = json_storage.DB_PATH
        self._set_db_path(self.path)
        self.addCleanup(self._restore_db_path)

        parser = argparse.ArgumentParser(prog="main.py")
        task.register(parser.add_subparsers(dest="command"))
        self.parser = parser

        real_load = json_storage.load
        real_save = json_storage.save
        load_patcher = mock.patch.object(json_storage, "load", wraps=real_load)
        save_patcher = mock.patch.object(json_storage, "save", wraps=real_save)
        self.load_mock = load_patcher.start()
        self.save_mock = save_patcher.start()
        self.addCleanup(load_patcher.stop)
        self.addCleanup(save_patcher.stop)

    def _set_db_path(self, path):
        env = os.environ.copy()
        if path is None:
            env.pop("HABIT_LOGGER_DB", None)
        else:
            env["HABIT_LOGGER_DB"] = path
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(json_storage)

    def _restore_db_path(self):
        self._set_db_path(self.original_env)
        self.assertEqual(json_storage.DB_PATH, self.original_db_path)

    def parse(self, *argv):
        """Parse *argv* with the test parser."""
        return self.parser.parse_args(argv)

    def run_handler(self, handler, args):
        """Run *handler* and return its code, stdout, and stderr."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = handler(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def run_main(self, argv):
        """Run main.main() and return its code, stdout, and stderr."""
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def write_db(self, payload):
        """Write *payload* to the temporary database file."""
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4)
            handle.write("\n")

    def write_raw(self, text):
        """Write raw *text* to the temporary database file."""
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def read_db(self):
        """Read and parse the temporary database file."""
        with open(self.path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def read_bytes(self):
        """Return the raw bytes of the temporary database file."""
        with open(self.path, "rb") as handle:
            return handle.read()

    def reset_mocks(self):
        """Clear recorded storage calls between subtests."""
        self.load_mock.reset_mock()
        self.save_mock.reset_mock()


class RegistrationTests(TaskCommandTestCase):
    def test_module_level_api_is_callable(self):
        names = (
            "register",
            "handle_task_add",
            "handle_task_list",
            "handle_task_complete",
            "handle_task_uncomplete",
            "handle_task_delete",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(task, name)))

    def test_task_help_lists_exactly_the_five_actions(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                self.parser.parse_args(["task", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("{add,list,complete,uncomplete,delete}", stdout.getvalue())

    def test_action_parsers_select_handlers_and_keep_id_as_string(self):
        cases = (
            (["task", "add", "Study"], task.handle_task_add),
            (["task", "list"], task.handle_task_list),
            (["task", "complete", "abc"], task.handle_task_complete),
            (["task", "uncomplete", "0"], task.handle_task_uncomplete),
            (["task", "delete", "-1"], task.handle_task_delete),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertIs(self.parse(*argv).func, expected)

        self.assertEqual(self.parse("task", "add", "Study").name, "Study")
        for action in ("complete", "uncomplete", "delete"):
            args = self.parse("task", action, "abc")
            self.assertIsInstance(args.task_id, str)
            self.assertEqual(args.task_id, "abc")


class AddCommandTests(TaskCommandTestCase):
    def test_add_loads_saves_once_and_prints_confirmation(self):
        args = self.parse("task", "add", "Study")
        code, stdout, stderr = self.run_handler(task.handle_task_add, args)

        expected = {
            "tasks": [{"id": 1, "name": "Study", "completed": False}],
            "habits": [],
            "next_task_id": 2,
            "next_habit_id": 1,
        }
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added task 1: Study\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_add_preserves_surrounding_spaces_verbatim(self):
        args = self.parse("task", "add", " Study ")
        code, stdout, stderr = self.run_handler(task.handle_task_add, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added task 1:  Study \n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.read_db()["tasks"][0]["name"], " Study ")

    def test_add_preserves_unicode_name(self):
        name = "Réviser — écrire"
        args = self.parse("task", "add", name)
        code, stdout, stderr = self.run_handler(task.handle_task_add, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, f"Added task 1: {name}\n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.read_db()["tasks"][0]["name"], name)

    def test_blank_names_fail_without_saving(self):
        for name in ("", "   "):
            with self.subTest(name=name):
                self.reset_mocks()
                args = self.parse("task", "add", name)
                code, stdout, stderr = self.run_handler(
                    task.handle_task_add, args
                )

                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "Task name must be a non-empty string.\n")
                self.load_mock.assert_called_once_with()
                self.save_mock.assert_not_called()
                self.assertFalse(os.path.exists(self.path))


class ListCommandTests(TaskCommandTestCase):
    def test_list_prints_all_tasks_in_order_without_saving(self):
        db = populated_db()
        self.write_db(db)
        args = self.parse("task", "list")
        code, stdout, stderr = self.run_handler(task.handle_task_list, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "1: Study [pending]\n2: Exercise [completed]\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_db(), db)

    def test_empty_list_prints_message_and_creates_no_file(self):
        self.assertFalse(os.path.exists(self.path))
        args = self.parse("task", "list")
        code, stdout, stderr = self.run_handler(task.handle_task_list, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "No tasks yet.\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.path))


class CompleteCommandTests(TaskCommandTestCase):
    def test_complete_loads_saves_once_and_prints_confirmation(self):
        self.write_db(populated_db())
        args = self.parse("task", "complete", "1")
        code, stdout, stderr = self.run_handler(task.handle_task_complete, args)

        expected = populated_db()
        expected["tasks"][0]["completed"] = True
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Completed task 1: Study\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_repeated_complete_is_idempotent(self):
        db = populated_db()
        db["tasks"][0]["completed"] = True
        self.write_db(db)
        before = self.read_bytes()
        args = self.parse("task", "complete", "1")

        for _ in range(2):
            self.reset_mocks()
            code, stdout, stderr = self.run_handler(
                task.handle_task_complete, args
            )

            self.assertEqual(code, 0)
            self.assertEqual(stdout, "Completed task 1: Study\n")
            self.assertEqual(stderr, "")
            self.load_mock.assert_called_once_with()
            self.save_mock.assert_called_once()
            self.assertEqual(self.read_bytes(), before)


class UncompleteCommandTests(TaskCommandTestCase):
    def test_uncomplete_loads_saves_once_and_prints_confirmation(self):
        db = populated_db()
        db["tasks"][0]["completed"] = True
        self.write_db(db)
        args = self.parse("task", "uncomplete", "1")
        code, stdout, stderr = self.run_handler(task.handle_task_uncomplete, args)

        expected = populated_db()
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Uncompleted task 1: Study\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_repeated_uncomplete_is_idempotent(self):
        self.write_db(populated_db())
        before = self.read_bytes()
        args = self.parse("task", "uncomplete", "1")

        for _ in range(2):
            self.reset_mocks()
            code, stdout, stderr = self.run_handler(
                task.handle_task_uncomplete, args
            )

            self.assertEqual(code, 0)
            self.assertEqual(stdout, "Uncompleted task 1: Study\n")
            self.assertEqual(stderr, "")
            self.load_mock.assert_called_once_with()
            self.save_mock.assert_called_once()
            self.assertEqual(self.read_bytes(), before)


class DeleteCommandTests(TaskCommandTestCase):
    def test_delete_loads_saves_once_and_prints_confirmation(self):
        self.write_db(populated_db())
        args = self.parse("task", "delete", "1")
        code, stdout, stderr = self.run_handler(task.handle_task_delete, args)

        expected = populated_db()
        expected["tasks"] = [{"id": 2, "name": "Exercise", "completed": True}]
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Deleted task 1: Study\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_next_add_uses_higher_id_after_delete(self):
        self.write_db(populated_db())
        self.run_handler(
            task.handle_task_delete, self.parse("task", "delete", "1")
        )
        self.reset_mocks()

        args = self.parse("task", "add", "New")
        code, stdout, stderr = self.run_handler(task.handle_task_add, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added task 3: New\n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.read_db()["tasks"][-1]["id"], 3)
        self.assertEqual(self.read_db()["next_task_id"], 4)


class InvalidTaskIdTests(TaskCommandTestCase):
    HANDLERS = (
        ("complete", task.handle_task_complete),
        ("uncomplete", task.handle_task_uncomplete),
        ("delete", task.handle_task_delete),
    )
    VALUES = ("abc", "0", "-1", "42")

    def test_invalid_ids_report_value_return_one_and_do_not_save(self):
        self.write_db(populated_db())
        before = self.read_bytes()

        for action, handler in self.HANDLERS:
            for value in self.VALUES:
                with self.subTest(action=action, value=value):
                    self.reset_mocks()
                    args = self.parse("task", action, value)
                    code, stdout, stderr = self.run_handler(handler, args)

                    self.assertEqual(code, 1)
                    self.assertEqual(stdout, "")
                    self.assertEqual(stderr.count("\n"), 1)
                    self.assertIn(value, stderr)
                    self.save_mock.assert_not_called()
                    self.assertEqual(self.read_bytes(), before)


class LoadErrorTests(TaskCommandTestCase):
    def test_load_value_error_is_reported_without_traceback_or_save(self):
        cases = (
            ("{not json", "Invalid JSON"),
            (json.dumps({"tasks": []}), "missing key"),
        )
        handlers = (
            (task.handle_task_add, self.parse("task", "add", "Study")),
            (task.handle_task_list, self.parse("task", "list")),
            (task.handle_task_complete, self.parse("task", "complete", "1")),
            (task.handle_task_uncomplete, self.parse("task", "uncomplete", "1")),
            (task.handle_task_delete, self.parse("task", "delete", "1")),
        )

        for text, fragment in cases:
            self.write_raw(text)
            before = self.read_bytes()
            for handler, args in handlers:
                with self.subTest(text=text, handler=handler.__name__):
                    self.reset_mocks()
                    code, stdout, stderr = self.run_handler(handler, args)

                    self.assertEqual(code, 1)
                    self.assertEqual(stdout, "")
                    self.assertIn(fragment, stderr)
                    self.assertEqual(stderr.count("\n"), 1)
                    self.save_mock.assert_not_called()
                    self.assertEqual(self.read_bytes(), before)


class MainWiringTests(TaskCommandTestCase):
    def test_main_without_command_returns_zero(self):
        code, stdout, stderr = self.run_main([])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.load_mock.assert_not_called()
        self.save_mock.assert_not_called()

    def test_main_dispatches_task_add(self):
        code, stdout, stderr = self.run_main(["task", "add", "Study"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added task 1: Study\n")
        self.assertEqual(stderr, "")
        self.save_mock.assert_called_once()
        self.assertEqual(self.read_db()["tasks"][0]["name"], "Study")


if __name__ == "__main__":
    unittest.main()
