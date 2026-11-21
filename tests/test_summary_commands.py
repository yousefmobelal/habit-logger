"""Tests for the summary CLI command."""

import argparse
import importlib
import inspect
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import date
from unittest import mock

from commands import summary
from main import main
from services import summary_service
from storage import json_storage as storage

TODAY = "2026-11-21"


def empty_db():
    """Return a new, empty database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def populated_db():
    """Return 3 tasks (2 complete) and 3 habits (2 logged on TODAY)."""
    return {
        "tasks": [
            {"id": 1, "name": "Study", "completed": True},
            {"id": 2, "name": "Exercise", "completed": False},
            {"id": 3, "name": "Read", "completed": True},
        ],
        "habits": [
            {"id": 1, "name": "Read", "logs": ["2026-11-20", TODAY]},
            {"id": 2, "name": "Meditate", "logs": [TODAY]},
            {"id": 3, "name": "Write", "logs": ["2026-11-19"]},
        ],
        "next_task_id": 4,
        "next_habit_id": 4,
    }


def render_counts(counts):
    """Render the five required output lines for *counts*."""
    return (
        f"Total tasks: {counts['total_tasks']}\n"
        f"Pending tasks: {counts['pending_tasks']}\n"
        f"Completed tasks: {counts['completed_tasks']}\n"
        f"Total habits: {counts['total_habits']}\n"
        f"Habits logged today: {counts['habits_logged_today']}\n"
    )


class SummaryCommandTestCase(unittest.TestCase):
    """Shared parser, temporary database, and output helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "db.json")
        self.assertEqual(os.path.dirname(self.path), self.temp_dir.name)
        self.assertNotEqual(
            os.path.abspath(self.path), os.path.abspath("data/db.json")
        )
        self.original_env = os.environ.get("HABIT_LOGGER_DB")
        self.original_db_path = storage.DB_PATH
        self._set_db_path(self.path)
        self.addCleanup(self._restore_db_path)

        parser = argparse.ArgumentParser(prog="main.py")
        summary.register(parser.add_subparsers(dest="command"))
        self.parser = parser

        self.real_load = summary.storage.load
        self.real_save = summary.storage.save
        load_patcher = mock.patch.object(summary.storage, "load", wraps=self.real_load)
        save_patcher = mock.patch.object(summary.storage, "save", wraps=self.real_save)
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
            importlib.reload(storage)

    def _restore_db_path(self):
        self._set_db_path(self.original_env)
        self.assertEqual(storage.DB_PATH, self.original_db_path)

    @contextmanager
    def fake_today(self, iso_date):
        """Patch the summary service's local date to *iso_date*."""
        with mock.patch.object(summary_service, "date") as mock_date:
            mock_date.today.return_value = date.fromisoformat(iso_date)
            yield mock_date

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

    def read_bytes(self):
        """Return the raw bytes of the temporary database file."""
        with open(self.path, "rb") as handle:
            return handle.read()

    def load_error_message(self):
        """Return the message produced by the real loader for the current file."""
        with self.assertRaises(ValueError) as caught:
            self.real_load()
        return str(caught.exception)

    def reset_mocks(self):
        """Clear recorded storage calls between subtests."""
        self.load_mock.reset_mock()
        self.save_mock.reset_mock()


class RegistrationTests(SummaryCommandTestCase):
    def test_module_api_and_storage_alias_are_callable(self):
        for name in ("register", "handle_summary"):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(summary, name)))
        self.assertIs(summary.storage, storage)

    def test_register_adds_summary_with_only_the_builtin_help_option(self):
        args = self.parse("summary")

        self.assertEqual(
            vars(args), {"command": "summary", "func": summary.handle_summary}
        )
        subparsers_action = next(
            action
            for action in self.parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        summary_parser = subparsers_action.choices["summary"]
        option_strings = [
            option
            for action in summary_parser._actions
            for option in action.option_strings
        ]
        positionals = [
            action.dest
            for action in summary_parser._actions
            if not action.option_strings
        ]
        self.assertEqual(option_strings, ["-h", "--help"])
        self.assertEqual(positionals, [])
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.parser.parse_args(["summary", "extra"])

    def test_summary_help_lists_only_summary_usage(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                self.parser.parse_args(["summary", "--help"])

        self.assertEqual(caught.exception.code, 0)
        output = stdout.getvalue()
        self.assertIn("usage: main.py summary [-h]", output)
        self.assertIn("--help", output)
        self.assertNotIn("{", output)


class EmptyDatabaseTests(SummaryCommandTestCase):
    EXPECTED = render_counts(
        {
            "total_tasks": 0,
            "pending_tasks": 0,
            "completed_tasks": 0,
            "total_habits": 0,
            "habits_logged_today": 0,
        }
    )

    def test_missing_file_prints_zeros_and_creates_no_file(self):
        self.assertFalse(os.path.exists(self.path))
        args = self.parse("summary")
        with mock.patch.object(
            summary_service, "get_summary", wraps=summary_service.get_summary
        ) as get_mock:
            code, stdout, stderr = self.run_handler(summary.handle_summary, args)

        call_args, call_kwargs = get_mock.call_args
        get_mock.assert_called_once()
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0], empty_db())
        self.assertEqual(call_kwargs, {})
        self.assertIs(type(code), int)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, self.EXPECTED)
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.path))

    def test_empty_file_prints_zeros_and_leaves_file_bytes_unchanged(self):
        self.write_db(empty_db())
        before = self.read_bytes()
        args = self.parse("summary")

        code, stdout, stderr = self.run_handler(summary.handle_summary, args)

        self.assertEqual(code, 0)
        self.assertEqual(stdout, self.EXPECTED)
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)


class PopulatedDatabaseTests(SummaryCommandTestCase):
    def test_prints_exact_lines_from_service_using_call_time_date(self):
        db = populated_db()
        self.write_db(db)
        before = self.read_bytes()
        expected = summary_service.get_summary(db, TODAY)
        self.assertEqual(
            expected,
            {
                "total_tasks": 3,
                "pending_tasks": 1,
                "completed_tasks": 2,
                "total_habits": 3,
                "habits_logged_today": 2,
            },
        )
        args = self.parse("summary")

        with self.fake_today(TODAY) as mock_date:
            with mock.patch.object(
                summary_service, "get_summary", wraps=summary_service.get_summary
            ) as get_mock:
                code, stdout, stderr = self.run_handler(
                    summary.handle_summary, args
                )

        mock_date.today.assert_called_once_with()
        call_args, call_kwargs = get_mock.call_args
        get_mock.assert_called_once()
        self.assertEqual(len(call_args), 1)
        self.assertEqual(call_args[0], db)
        self.assertEqual(call_kwargs, {})
        self.assertIs(type(code), int)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, render_counts(expected))
        self.assertEqual(
            stdout,
            "Total tasks: 3\n"
            "Pending tasks: 1\n"
            "Completed tasks: 2\n"
            "Total habits: 3\n"
            "Habits logged today: 2\n",
        )
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)


class ReadOnlyTests(SummaryCommandTestCase):
    def test_repeated_runs_never_save_or_change_file_bytes(self):
        raw = json.dumps(populated_db(), indent=2)
        self.write_raw(raw)
        before = self.read_bytes()
        args = self.parse("summary")

        for _ in range(2):
            self.reset_mocks()
            with self.fake_today(TODAY):
                code, stdout, stderr = self.run_handler(
                    summary.handle_summary, args
                )

            self.assertEqual(code, 0)
            self.assertTrue(stdout)
            self.assertEqual(stderr, "")
            self.load_mock.assert_called_once_with()
            self.save_mock.assert_not_called()
            self.assertEqual(self.read_bytes(), before)

    def test_command_module_has_no_direct_file_io(self):
        source = inspect.getsource(summary).lower()
        for name in ("open", "json", "os", "pathlib"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(summary, name))
                self.assertNotRegex(source, rf"\b{name}\b")


class LoadErrorTests(SummaryCommandTestCase):
    def test_real_load_errors_are_reported_verbatim_without_traceback(self):
        cases = (
            "{not json",
            "[]",
            json.dumps({"tasks": []}),
            json.dumps(
                {
                    "tasks": {},
                    "habits": [],
                    "next_task_id": 1,
                    "next_habit_id": 1,
                }
            ),
            json.dumps(
                {
                    "tasks": [],
                    "habits": {},
                    "next_task_id": 1,
                    "next_habit_id": 1,
                }
            ),
        )
        args = self.parse("summary")

        for text in cases:
            with self.subTest(text=text):
                self.write_raw(text)
                before = self.read_bytes()
                message = self.load_error_message()
                self.reset_mocks()
                with mock.patch.object(
                    summary_service, "get_summary", wraps=summary_service.get_summary
                ) as get_mock:
                    code, stdout, stderr = self.run_handler(
                        summary.handle_summary, args
                    )

                get_mock.assert_not_called()
                self.assertIs(type(code), int)
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, f"{message}\n")
                self.assertEqual(stderr.count("\n"), 1)
                self.assertNotIn("Traceback", stderr)
                self.load_mock.assert_called_once_with()
                self.save_mock.assert_not_called()
                self.assertEqual(self.read_bytes(), before)

    def test_value_error_from_load_is_printed_verbatim(self):
        self.write_db(populated_db())
        before = self.read_bytes()
        message = "load failed: <verbatim> 42"
        args = self.parse("summary")

        with mock.patch.object(
            summary.storage, "load", side_effect=ValueError(message)
        ) as forced_load:
            with mock.patch.object(summary_service, "get_summary") as get_mock:
                code, stdout, stderr = self.run_handler(
                    summary.handle_summary, args
                )

        forced_load.assert_called_once_with()
        get_mock.assert_not_called()
        self.assertIs(type(code), int)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, f"{message}\n")
        self.assertNotIn("Traceback", stderr)
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)


class MainWiringTests(SummaryCommandTestCase):
    def test_main_help_lists_summary_without_touching_storage(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                main(["--help"])

        self.assertEqual(caught.exception.code, 0)
        self.assertIn("summary", stdout.getvalue())
        self.load_mock.assert_not_called()
        self.save_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.path))

    def test_main_dispatches_summary_to_the_handler(self):
        self.write_db(populated_db())
        before = self.read_bytes()
        with self.fake_today(TODAY), mock.patch.object(
            summary, "handle_summary", wraps=summary.handle_summary
        ) as handler_mock:
            code, stdout, stderr = self.run_main(["summary"])

        handler_mock.assert_called_once()
        self.assertIsInstance(handler_mock.call_args[0][0], argparse.Namespace)
        self.assertIs(type(code), int)
        self.assertEqual(code, 0)
        self.assertEqual(
            stdout,
            "Total tasks: 3\n"
            "Pending tasks: 1\n"
            "Completed tasks: 2\n"
            "Total habits: 3\n"
            "Habits logged today: 2\n",
        )
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)

    def test_main_returns_the_handlers_integer_code(self):
        with mock.patch.object(summary, "handle_summary", return_value=7) as handler:
            code, stdout, stderr = self.run_main(["summary"])

        handler.assert_called_once()
        self.assertEqual(code, 7)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.load_mock.assert_not_called()
        self.save_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
