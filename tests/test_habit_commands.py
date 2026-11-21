"""Tests for the habit CLI commands."""

import argparse
import copy
import importlib
import io
import json
import os
import tempfile
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import date
from unittest import mock

from commands import habit
from main import main
from services import habit_service
from storage import json_storage as storage


def empty_db():
    """Return a new, empty database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def habit_db():
    """Return a database with two habits and unrelated task data."""
    return {
        "tasks": [{"id": 1, "name": "Study", "completed": False}],
        "habits": [
            {"id": 1, "name": "Read", "logs": ["2026-11-20"]},
            {"id": 2, "name": "Workout", "logs": []},
        ],
        "next_task_id": 2,
        "next_habit_id": 3,
    }


class HabitCommandTestCase(unittest.TestCase):
    """Shared parser, temporary database, and output helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "db.json")
        self.original_env = os.environ.get("HABIT_LOGGER_DB")
        self.original_db_path = storage.DB_PATH
        self._set_db_path(self.path)
        self.addCleanup(self._restore_db_path)

        parser = argparse.ArgumentParser(prog="main.py")
        habit.register(parser.add_subparsers(dest="command"))
        self.parser = parser

        real_load = habit.storage.load
        real_save = habit.storage.save
        load_patcher = mock.patch.object(habit.storage, "load", wraps=real_load)
        save_patcher = mock.patch.object(habit.storage, "save", wraps=real_save)
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
        """Patch the service's local date to *iso_date* for one block."""
        with mock.patch("services.habit_service.date") as mock_date:
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


class RegistrationTests(HabitCommandTestCase):
    def test_module_level_api_is_callable(self):
        names = (
            "register",
            "handle_habit_add",
            "handle_habit_list",
            "handle_habit_log",
            "handle_habit_delete",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(habit, name)))
        self.assertIs(habit.storage, storage)

    def test_help_lists_exactly_the_four_actions(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                self.parser.parse_args(["habit", "--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("{add,list,log,delete}", stdout.getvalue())

    def test_action_parsers_select_handlers_and_keep_values_verbatim(self):
        cases = (
            (["habit", "add", "Read 30 minutes"], habit.handle_habit_add),
            (["habit", "list"], habit.handle_habit_list),
            (["habit", "log", "1"], habit.handle_habit_log),
            (["habit", "delete", "1"], habit.handle_habit_delete),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                self.assertIs(self.parse(*argv).func, expected)

        name = "Read 30 minutes"
        self.assertEqual(self.parse("habit", "add", name).name, name)
        for action in ("log", "delete"):
            args = self.parse("habit", action, "abc")
            self.assertIsInstance(args.habit_id, str)
            self.assertEqual(args.habit_id, "abc")

        args = self.parse("habit", "list")
        self.assertEqual(args.habit_action, "list")
        self.assertFalse(hasattr(args, "name"))
        self.assertFalse(hasattr(args, "habit_id"))
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.parser.parse_args(["habit", "list", "extra"])

    def test_success_handlers_return_plain_int(self):
        cases = (
            (habit.handle_habit_add, self.parse("habit", "add", "Read")),
            (habit.handle_habit_list, self.parse("habit", "list")),
            (habit.handle_habit_log, self.parse("habit", "log", "1")),
            (habit.handle_habit_delete, self.parse("habit", "delete", "1")),
        )
        for handler, args in cases:
            with self.subTest(handler=handler.__name__):
                self.write_db(habit_db())
                self.reset_mocks()
                with self.fake_today("2026-11-21"):
                    code, _, _ = self.run_handler(handler, args)
                self.assertIs(type(code), int)
                self.assertEqual(code, 0)

    def test_error_handlers_return_plain_int(self):
        self.write_db(habit_db())
        before = self.read_bytes()
        cases = (
            (habit.handle_habit_add, argparse.Namespace(name="   ")),
            (habit.handle_habit_log, self.parse("habit", "log", "abc")),
            (habit.handle_habit_delete, self.parse("habit", "delete", "42")),
        )
        for handler, args in cases:
            with self.subTest(handler=handler.__name__):
                self.reset_mocks()
                code, _, _ = self.run_handler(handler, args)
                self.assertIs(type(code), int)
                self.assertEqual(code, 1)
                self.assertEqual(self.read_bytes(), before)


class AddCommandTests(HabitCommandTestCase):
    def test_add_loads_saves_once_and_prints_confirmation(self):
        self.assertFalse(os.path.exists(self.path))
        args = self.parse("habit", "add", "Read")
        with mock.patch.object(
            habit_service, "add", wraps=habit_service.add
        ) as add_mock:
            code, stdout, stderr = self.run_handler(habit.handle_habit_add, args)

        expected = {
            "tasks": [],
            "habits": [{"id": 1, "name": "Read", "logs": []}],
            "next_task_id": 1,
            "next_habit_id": 2,
        }
        add_mock.assert_called_once()
        self.assertEqual(add_mock.call_args[0][1], "Read")
        self.assertIs(type(code), int)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added habit 1: Read\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_duplicate_names_get_distinct_ids_and_both_appear_in_list(self):
        for expected_id, name in ((1, "Read"), (2, "Read")):
            with self.subTest(name=name, expected_id=expected_id):
                self.reset_mocks()
                code, stdout, stderr = self.run_handler(
                    habit.handle_habit_add, self.parse("habit", "add", name)
                )
                self.assertEqual(code, 0)
                self.assertEqual(stdout, f"Added habit {expected_id}: {name}\n")
                self.assertEqual(stderr, "")
                self.save_mock.assert_called_once()

        db = self.read_db()
        self.assertEqual([item["id"] for item in db["habits"]], [1, 2])
        self.assertEqual([item["name"] for item in db["habits"]], ["Read", "Read"])
        self.assertEqual(db["next_habit_id"], 3)

        self.reset_mocks()
        code, stdout, stderr = self.run_handler(
            habit.handle_habit_list, self.parse("habit", "list")
        )
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "1: Read\n2: Read\n")
        self.assertEqual(stderr, "")
        self.save_mock.assert_not_called()

    def test_add_preserves_name_verbatim(self):
        for name in ("  Read  ", "Réviser — lire"):
            with self.subTest(name=name):
                self.write_db(empty_db())
                self.reset_mocks()
                args = self.parse("habit", "add", name)
                code, stdout, stderr = self.run_handler(
                    habit.handle_habit_add, args
                )
                self.assertEqual(code, 0)
                self.assertEqual(stdout, f"Added habit 1: {name}\n")
                self.assertEqual(stderr, "")
                self.assertEqual(self.read_db()["habits"][0]["name"], name)

    def test_blank_and_non_string_names_fail_without_saving(self):
        for name in ("", "   ", None):
            with self.subTest(name=name):
                self.reset_mocks()
                if name is None:
                    args = argparse.Namespace(name=None)
                else:
                    args = self.parse("habit", "add", name)
                code, stdout, stderr = self.run_handler(
                    habit.handle_habit_add, args
                )
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "Habit name must be a non-empty string.\n")
                self.load_mock.assert_called_once_with()
                self.save_mock.assert_not_called()
                self.assertFalse(os.path.exists(self.path))


class ListCommandTests(HabitCommandTestCase):
    def test_list_prints_habits_in_order_without_saving(self):
        db = habit_db()
        self.write_db(db)
        with mock.patch.object(
            habit_service, "list_habits", wraps=habit_service.list_habits
        ) as list_mock:
            code, stdout, stderr = self.run_handler(
                habit.handle_habit_list, self.parse("habit", "list")
            )

        list_mock.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "1: Read\n2: Workout\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_db(), db)

    def test_empty_list_prints_message_and_creates_no_file(self):
        self.assertFalse(os.path.exists(self.path))
        code, stdout, stderr = self.run_handler(
            habit.handle_habit_list, self.parse("habit", "list")
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "No habits yet.\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.path))


class LogCommandTests(HabitCommandTestCase):
    def test_log_uses_service_date_saves_once_and_prints_exact_line(self):
        self.write_db(habit_db())
        args = self.parse("habit", "log", "1")
        with self.fake_today("2026-11-21") as mock_date:
            with mock.patch.object(
                habit_service, "log", wraps=habit_service.log
            ) as log_mock:
                code, stdout, stderr = self.run_handler(
                    habit.handle_habit_log, args
                )

        mock_date.today.assert_called_once_with()
        log_mock.assert_called_once()
        call_args, call_kwargs = log_mock.call_args
        self.assertEqual(len(call_args), 2)
        self.assertEqual(call_args[1], 1)
        self.assertEqual(call_kwargs, {})
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Logged habit 1: Read on 2026-11-21\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once()
        self.assertEqual(
            self.read_db()["habits"][0]["logs"],
            ["2026-11-20", "2026-11-21"],
        )

    def test_second_log_on_a_different_date_appends_in_order(self):
        db = {
            "tasks": [],
            "habits": [{"id": 1, "name": "Read", "logs": []}],
            "next_task_id": 1,
            "next_habit_id": 2,
        }
        self.write_db(db)
        args = self.parse("habit", "log", "1")
        with self.fake_today("2026-11-21"):
            first = self.run_handler(habit.handle_habit_log, args)
        self.reset_mocks()
        with self.fake_today("2026-11-22"):
            second = self.run_handler(habit.handle_habit_log, args)

        self.assertEqual(first[0], 0)
        self.assertEqual(first[1], "Logged habit 1: Read on 2026-11-21\n")
        self.assertEqual(second[0], 0)
        self.assertEqual(second[1], "Logged habit 1: Read on 2026-11-22\n")
        self.assertEqual(second[2], "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once()
        self.assertEqual(
            self.read_db()["habits"][0]["logs"],
            ["2026-11-21", "2026-11-22"],
        )

    def test_second_log_on_same_day_is_rejected_without_touching_file(self):
        db = {
            "tasks": [],
            "habits": [{"id": 1, "name": "Read", "logs": []}],
            "next_task_id": 1,
            "next_habit_id": 2,
        }
        self.write_db(db)
        args = self.parse("habit", "log", "1")
        with self.fake_today("2026-11-21"):
            self.run_handler(habit.handle_habit_log, args)
        before = self.read_bytes()
        self.reset_mocks()
        with self.fake_today("2026-11-21"):
            code, stdout, stderr = self.run_handler(
                habit.handle_habit_log, args
            )

        self.assertIs(type(code), int)
        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Habit 'Read' is already logged on 2026-11-21.\n")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)

    def test_duplicate_day_message_uses_repr_for_apostrophe_names(self):
        db = {
            "tasks": [],
            "habits": [{"id": 1, "name": "Bob's", "logs": ["2026-11-21"]}],
            "next_task_id": 1,
            "next_habit_id": 2,
        }
        self.write_db(db)
        before = self.read_bytes()
        args = self.parse("habit", "log", "1")
        with self.fake_today("2026-11-21"):
            code, stdout, stderr = self.run_handler(
                habit.handle_habit_log, args
            )

        self.assertEqual(code, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Habit \"Bob's\" is already logged on 2026-11-21.\n")
        self.save_mock.assert_not_called()
        self.assertEqual(self.read_bytes(), before)


class InvalidIdTests(HabitCommandTestCase):
    def test_log_and_delete_reject_invalid_ids_without_saving(self):
        self.write_db(habit_db())
        before = self.read_bytes()
        cases = (
            (habit.handle_habit_log, "log", "abc", None, 0),
            (habit.handle_habit_delete, "delete", "abc", None, 0),
            (
                habit.handle_habit_log,
                "log",
                "0",
                "Habit id must be a positive integer, got 0.\n",
                1,
            ),
            (
                habit.handle_habit_log,
                "log",
                "-1",
                "Habit id must be a positive integer, got -1.\n",
                1,
            ),
            (
                habit.handle_habit_delete,
                "delete",
                "0",
                "Habit id must be a positive integer, got 0.\n",
                1,
            ),
            (
                habit.handle_habit_delete,
                "delete",
                "42",
                "No habit found with id 42.\n",
                1,
            ),
        )
        for handler, action, value, expected, expected_loads in cases:
            with self.subTest(handler=handler.__name__, value=value):
                self.reset_mocks()
                args = self.parse("habit", action, value)
                code, stdout, stderr = self.run_handler(handler, args)

                self.assertIs(type(code), int)
                self.assertEqual(code, 1)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr.count("\n"), 1)
                self.assertTrue(stderr)
                if expected is None:
                    self.assertIn(value, stderr)
                else:
                    self.assertEqual(stderr, expected)
                self.assertEqual(self.load_mock.call_count, expected_loads)
                self.save_mock.assert_not_called()
                self.assertEqual(self.read_bytes(), before)


class DeleteCommandTests(HabitCommandTestCase):
    def test_delete_removes_only_target_habit_and_saves_once(self):
        db = habit_db()
        self.write_db(db)
        args = self.parse("habit", "delete", "1")
        with mock.patch.object(
            habit_service, "delete", wraps=habit_service.delete
        ) as delete_mock:
            code, stdout, stderr = self.run_handler(
                habit.handle_habit_delete, args
            )

        expected = copy.deepcopy(db)
        expected["habits"] = [db["habits"][1]]
        delete_mock.assert_called_once()
        self.assertEqual(delete_mock.call_args[0][1], 1)
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Deleted habit 1: Read\n")
        self.assertEqual(stderr, "")
        self.load_mock.assert_called_once_with()
        self.save_mock.assert_called_once_with(expected)
        self.assertEqual(self.read_db(), expected)

    def test_next_add_uses_next_unused_id_after_delete(self):
        self.write_db(habit_db())
        self.run_handler(
            habit.handle_habit_delete, self.parse("habit", "delete", "1")
        )
        self.reset_mocks()
        code, stdout, stderr = self.run_handler(
            habit.handle_habit_add, self.parse("habit", "add", "Meditate")
        )

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added habit 3: Meditate\n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.read_db()["habits"][-1]["id"], 3)
        self.assertEqual(self.read_db()["next_habit_id"], 4)


class LoadErrorTests(HabitCommandTestCase):
    def test_load_value_errors_are_reported_without_traceback_or_save(self):
        cases = (
            ("{not json", "Invalid JSON"),
            (json.dumps({"habits": []}), "missing key"),
            (
                json.dumps(
                    {
                        "tasks": [],
                        "habits": {},
                        "next_task_id": 1,
                        "next_habit_id": 1,
                    }
                ),
                "must be a list",
            ),
        )
        handlers = (
            (habit.handle_habit_add, self.parse("habit", "add", "Read")),
            (habit.handle_habit_list, self.parse("habit", "list")),
            (habit.handle_habit_log, self.parse("habit", "log", "1")),
            (habit.handle_habit_delete, self.parse("habit", "delete", "1")),
        )

        for text, fragment in cases:
            self.write_raw(text)
            before = self.read_bytes()
            for handler, args in handlers:
                with self.subTest(text=fragment, handler=handler.__name__):
                    self.reset_mocks()
                    code, stdout, stderr = self.run_handler(handler, args)

                    self.assertIs(type(code), int)
                    self.assertEqual(code, 1)
                    self.assertEqual(stdout, "")
                    self.assertIn(fragment, stderr)
                    self.assertEqual(stderr.count("\n"), 1)
                    self.load_mock.assert_called_once_with()
                    self.save_mock.assert_not_called()
                    self.assertEqual(self.read_bytes(), before)


class PurityTests(HabitCommandTestCase):
    def test_mutating_handlers_preserve_unrelated_data(self):
        baseline = habit_db()
        cases = (
            (habit.handle_habit_add, self.parse("habit", "add", "New")),
            (habit.handle_habit_log, self.parse("habit", "log", "1")),
            (habit.handle_habit_delete, self.parse("habit", "delete", "1")),
        )
        for handler, args in cases:
            with self.subTest(handler=handler.__name__):
                self.write_db(copy.deepcopy(baseline))
                self.reset_mocks()
                with self.fake_today("2026-11-21"):
                    code, _, _ = self.run_handler(handler, args)
                saved = self.read_db()

                self.assertEqual(code, 0)
                self.assertEqual(set(saved), set(baseline))
                self.assertEqual(saved["tasks"], baseline["tasks"])
                self.assertEqual(saved["next_task_id"], baseline["next_task_id"])
                expected_next = 4 if handler is habit.handle_habit_add else 3
                self.assertEqual(saved["next_habit_id"], expected_next)
                other = [item for item in saved["habits"] if item["id"] == 2]
                self.assertEqual(other, [baseline["habits"][1]])

    def test_handlers_do_not_call_open_directly(self):
        self.write_db(habit_db())
        cases = (
            (habit.handle_habit_add, self.parse("habit", "add", "New")),
            (habit.handle_habit_list, self.parse("habit", "list")),
            (habit.handle_habit_log, self.parse("habit", "log", "1")),
            (habit.handle_habit_delete, self.parse("habit", "delete", "1")),
        )
        for handler, args in cases:
            with self.subTest(handler=handler.__name__):
                self.reset_mocks()
                with mock.patch.object(
                    habit.storage, "load", return_value=copy.deepcopy(habit_db())
                ), mock.patch.object(habit.storage, "save") as save_mock:
                    with mock.patch(
                        "builtins.open", side_effect=AssertionError("open called")
                    ) as open_mock:
                        code, _, _ = self.run_handler(handler, args)

                open_mock.assert_not_called()
                if handler is habit.handle_habit_list:
                    save_mock.assert_not_called()
                else:
                    save_mock.assert_called_once()
                self.assertEqual(code, 0)

    def test_command_module_has_no_direct_io_helpers(self):
        for name in ("open", "json", "os", "pathlib"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(habit, name))


class MainWiringTests(HabitCommandTestCase):
    def test_main_help_for_habit_lists_actions_without_storage_calls(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as caught:
                main(["habit", "--help"])

        output = stdout.getvalue()
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("{add,list,log,delete}", output)
        for action in ("add", "list", "log", "delete"):
            self.assertIn(action, output)
        self.load_mock.assert_not_called()
        self.save_mock.assert_not_called()
        self.assertFalse(os.path.exists(self.path))

    def test_main_dispatches_habit_add_to_handler(self):
        with mock.patch.object(
            habit, "handle_habit_add", wraps=habit.handle_habit_add
        ) as add_mock:
            code, stdout, stderr = self.run_main(
                ["habit", "add", "Read 30 minutes"]
            )

        add_mock.assert_called_once()
        self.assertEqual(add_mock.call_args[0][0].name, "Read 30 minutes")
        self.assertEqual(code, 0)
        self.assertEqual(stdout, "Added habit 1: Read 30 minutes\n")
        self.assertEqual(stderr, "")
        self.save_mock.assert_called_once()
        self.assertEqual(
            self.read_db()["habits"][0]["name"], "Read 30 minutes"
        )

    def test_main_still_dispatches_task_commands(self):
        code, stdout, stderr = self.run_main(["task", "list"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout, "No tasks yet.\n")
        self.assertEqual(stderr, "")


if __name__ == "__main__":
    unittest.main()
