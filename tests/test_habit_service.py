"""Tests for services.habit_service."""

import copy
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from unittest import mock

from services import habit_service


def fresh_db():
    """Return a new empty in-memory database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def populated_db():
    """Return a database with tasks, habits, logs, and advanced id counters."""
    return {
        "tasks": [
            {"id": 1, "name": "Study", "completed": False},
            {"id": 2, "name": "Exercise", "completed": True},
        ],
        "habits": [
            {"id": 1, "name": "Read", "logs": ["2026-11-20"]},
            {"id": 2, "name": "Meditate", "logs": []},
            {"id": 3, "name": "Write", "logs": ["2026-11-19", "2026-11-20"]},
        ],
        "next_task_id": 3,
        "next_habit_id": 4,
    }


class FixedDate:
    """Fake date instance with a fixed ISO string."""

    def __init__(self, iso_value):
        self.iso_value = iso_value

    def isoformat(self):
        return self.iso_value


class FixedTodayDate:
    """Fake date class whose today() returns a FixedDate."""

    def __init__(self, iso_value):
        self.iso_value = iso_value

    def today(self):
        return FixedDate(self.iso_value)


class HabitServiceTestCase(unittest.TestCase):
    """Shared assertions for rejected service calls."""

    def assert_rejected(self, operation, db, *args, field, value_fragment):
        before = copy.deepcopy(db)
        with self.assertRaises(ValueError) as caught:
            operation(db, *args)
        message = str(caught.exception)
        self.assertIn(field, message.lower())
        self.assertIn(value_fragment, message)
        self.assertEqual(db, before)
        return message


class HabitServiceApiTests(HabitServiceTestCase):
    def test_required_functions_are_module_level_and_callable(self):
        for name in ("add", "list_habits", "log", "delete"):
            with self.subTest(function=name):
                self.assertTrue(callable(getattr(habit_service, name)))


class AddHabitTests(HabitServiceTestCase):
    def test_add_to_fresh_db_returns_the_stored_habit(self):
        db = fresh_db()
        result = habit_service.add(db, "Read")

        self.assertIs(result, db["habits"][-1])
        self.assertEqual(result, {"id": 1, "name": "Read", "logs": []})
        self.assertEqual(db["habits"], [result])
        self.assertEqual(db["next_habit_id"], 2)
        self.assertEqual(db["tasks"], [])
        self.assertEqual(db["next_task_id"], 1)

    def test_second_add_gets_next_id(self):
        db = fresh_db()
        first = habit_service.add(db, "Read")
        second = habit_service.add(db, "Write")

        self.assertEqual((first["id"], second["id"]), (1, 2))
        self.assertIs(second, db["habits"][-1])
        self.assertEqual(db["next_habit_id"], 3)

    def test_delete_then_add_does_not_reuse_id(self):
        db = fresh_db()
        habit_service.add(db, "One")
        habit_service.add(db, "Two")
        habit_service.delete(db, 1)

        third = habit_service.add(db, "Three")

        self.assertEqual(third["id"], 3)
        self.assertEqual([habit["id"] for habit in db["habits"]], [2, 3])
        self.assertEqual(db["next_habit_id"], 4)

    def test_delete_highest_id_then_add_does_not_reuse_id(self):
        db = fresh_db()
        habit_service.add(db, "One")
        habit_service.add(db, "Two")
        habit_service.delete(db, 2)

        self.assertEqual(habit_service.add(db, "Three")["id"], 3)
        self.assertEqual(db["next_habit_id"], 4)

    def test_add_preserves_name_exactly_and_allows_duplicate_names(self):
        db = fresh_db()
        first = habit_service.add(db, " Read ")
        second = habit_service.add(db, " Read ")

        self.assertEqual(first["name"], " Read ")
        self.assertEqual(second["name"], " Read ")
        self.assertIsNot(first, second)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual([habit["id"] for habit in db["habits"]], [1, 2])

    def test_add_stores_unicode_and_punctuation_unchanged(self):
        db = fresh_db()
        name = "Lire — écrire: oui"

        self.assertEqual(habit_service.add(db, name)["name"], name)

    def test_invalid_names_raise_and_leave_db_unchanged(self):
        invalid_names = (
            "", "   ", "\t\n", None, 123, [], True, False, 1.5, {}, (),
        )
        for name in invalid_names:
            with self.subTest(name=name):
                db = populated_db()
                self.assert_rejected(
                    habit_service.add, db, name,
                    field="name", value_fragment="non-empty",
                )

    def test_failed_add_does_not_consume_an_id(self):
        db = fresh_db()
        with self.assertRaises(ValueError):
            habit_service.add(db, "   ")

        self.assertEqual(habit_service.add(db, "Read")["id"], 1)
        self.assertEqual(db["next_habit_id"], 2)


class ListHabitsTests(HabitServiceTestCase):
    def test_list_habits_returns_empty_list_for_empty_db(self):
        db = fresh_db()

        self.assertEqual(habit_service.list_habits(db), [])
        self.assertEqual(db, fresh_db())

    def test_list_habits_preserves_insertion_order_and_logs(self):
        db = populated_db()

        habits = habit_service.list_habits(db)

        self.assertEqual(habits, db["habits"])
        self.assertEqual([habit["name"] for habit in habits],
                         ["Read", "Meditate", "Write"])
        self.assertEqual(habits[2]["logs"], ["2026-11-19", "2026-11-20"])

    def test_list_habits_returns_the_stored_dict_objects(self):
        db = populated_db()

        habits = habit_service.list_habits(db)

        self.assertIsNot(habits, db["habits"])
        self.assertEqual(len(habits), len(db["habits"]))
        for actual, expected in zip(habits, db["habits"]):
            self.assertIs(actual, expected)
        self.assertIs(habits[0]["logs"], db["habits"][0]["logs"])

    def test_list_habits_does_not_mutate_db_even_if_result_is_changed(self):
        db = populated_db()
        before = copy.deepcopy(db)

        habits = habit_service.list_habits(db)
        habits.reverse()
        habits.clear()

        self.assertEqual(db, before)

    def test_list_habits_returns_only_habits_when_tasks_exist(self):
        db = populated_db()

        habits = habit_service.list_habits(db)

        self.assertEqual(habits, db["habits"])
        self.assertFalse(any("completed" in habit for habit in habits))


class LogHabitTests(HabitServiceTestCase):
    def test_default_today_uses_date_today_at_call_time(self):
        db = fresh_db()
        habit_service.add(db, "Read")

        with mock.patch.object(habit_service, "date") as mocked_date:
            mocked_date.today.return_value.isoformat.return_value = "2026-11-20"
            first = habit_service.log(db, 1)
        mocked_date.today.assert_called_once_with()

        with mock.patch.object(
            habit_service, "date", FixedTodayDate("2026-11-21")
        ):
            second = habit_service.log(db, 1)

        self.assertIs(first, db["habits"][0])
        self.assertIs(second, db["habits"][0])
        self.assertEqual(db["habits"][0]["logs"],
                         ["2026-11-20", "2026-11-21"])

    def test_explicit_none_matches_omitted_today(self):
        db = fresh_db()
        habit_service.add(db, "Read")
        habit_service.add(db, "Write")

        with mock.patch.object(
            habit_service, "date", FixedTodayDate("2026-11-21")
        ):
            first = habit_service.log(db, 1)
            second = habit_service.log(db, 2, today=None)

        self.assertIs(first, db["habits"][0])
        self.assertIs(second, db["habits"][1])
        self.assertEqual(db["habits"][0]["logs"], ["2026-11-21"])
        self.assertEqual(db["habits"][1]["logs"], ["2026-11-21"])

    def test_explicit_date_is_appended_without_changing_earlier_order(self):
        db = populated_db()
        habit = db["habits"][2]
        before = copy.deepcopy(habit["logs"])

        result = habit_service.log(db, 3, today="2026-11-21")

        self.assertIs(result, habit)
        self.assertEqual(habit["logs"], before + ["2026-11-21"])

    def test_different_dates_keep_the_order_they_were_logged_in(self):
        db = fresh_db()
        habit_service.add(db, "Read")

        habit_service.log(db, 1, today="2026-11-21")
        habit_service.log(db, 1, today="2026-11-20")

        self.assertEqual(db["habits"][0]["logs"],
                         ["2026-11-21", "2026-11-20"])

    def test_duplicate_day_raises_with_name_and_date_and_leaves_db_unchanged(
        self
    ):
        db = fresh_db()
        habit_service.add(db, "Read")
        habit_service.log(db, 1, today="2026-11-20")

        message = self.assert_rejected(
            habit_service.log, db, 1, "2026-11-20",
            field="read", value_fragment="2026-11-20",
        )

        self.assertIn("already", message.lower())

    def test_duplicate_day_rejection_is_per_habit(self):
        db = fresh_db()
        habit_service.add(db, "Read")
        habit_service.add(db, "Write")
        habit_service.log(db, 1, today="2026-11-20")
        habit_service.log(db, 2, today="2026-11-20")
        before = copy.deepcopy(db)

        self.assert_rejected(
            habit_service.log, db, 1, "2026-11-20",
            field="read", value_fragment="2026-11-20",
        )

        self.assertEqual(db["habits"][1]["logs"], ["2026-11-20"])
        self.assertEqual(db, before)

    def test_invalid_dates_raise_and_leave_db_unchanged(self):
        invalid_dates = (
            "2026-13-40",
            "21-11-2026",
            "",
            "2026-2-03",
            " 2026-11-20 ",
            "2026-11-21T00:00:00",
            "2026-02-29",
            date(2026, 11, 20),
            datetime(2026, 11, 20),
            20261121,
            [],
            True,
            False,
            1.5,
            {},
            (),
        )
        for value in invalid_dates:
            with self.subTest(today=value):
                db = fresh_db()
                habit_service.add(db, "Read")
                habit_service.log(db, 1, today="2026-11-19")

                self.assert_rejected(
                    habit_service.log, db, 1, value,
                    field="date", value_fragment=repr(value),
                )

    def test_valid_boundary_dates_are_accepted_verbatim(self):
        for value in ("2024-02-29", "2000-01-01"):
            with self.subTest(today=value):
                db = fresh_db()
                habit_service.add(db, "Read")

                result = habit_service.log(db, 1, today=value)

                self.assertIs(result, db["habits"][0])
                self.assertEqual(db["habits"][0]["logs"], [value])

    def test_log_does_not_accept_int_subclass_ids(self):
        class HabitId(int):
            pass

        db = fresh_db()
        habit_service.add(db, "Read")

        self.assert_rejected(
            habit_service.log, db, HabitId(1),
            field="id", value_fragment="positive integer",
        )


class InvalidHabitIdTests(HabitServiceTestCase):
    OPERATIONS = (habit_service.log, habit_service.delete)

    def test_invalid_ids_raise_and_leave_db_unchanged(self):
        invalid_ids = (None, "1", 1.0, 1.5, 0, -1, True, False)
        for operation in self.OPERATIONS:
            for habit_id in invalid_ids:
                with self.subTest(operation=operation.__name__, habit_id=habit_id):
                    db = populated_db()
                    self.assert_rejected(
                        operation, db, habit_id,
                        field="id", value_fragment=repr(habit_id),
                    )

    def test_int_subclass_is_not_a_plain_int(self):
        class HabitId(int):
            pass

        for operation in self.OPERATIONS:
            with self.subTest(operation=operation.__name__):
                db = populated_db()
                self.assert_rejected(
                    operation, db, HabitId(1),
                    field="id", value_fragment="positive integer",
                )

    def test_unknown_ids_raise_and_leave_db_unchanged(self):
        for operation in self.OPERATIONS:
            for db_factory in (fresh_db, populated_db):
                with self.subTest(operation=operation.__name__):
                    db = db_factory()
                    self.assert_rejected(
                        operation, db, 42,
                        field="id", value_fragment="42",
                    )


class DeleteHabitTests(HabitServiceTestCase):
    def test_delete_removes_only_target_and_returns_removed_dict(self):
        db = populated_db()
        before = copy.deepcopy(db)
        target = db["habits"][1]

        removed = habit_service.delete(db, 2)

        self.assertIs(removed, target)
        self.assertEqual(removed, before["habits"][1])
        expected = copy.deepcopy(before)
        del expected["habits"][1]
        self.assertEqual(db, expected)
        self.assertEqual([habit["id"] for habit in db["habits"]], [1, 3])
        self.assertEqual(db["next_habit_id"], 4)
        self.assertEqual(db["tasks"], before["tasks"])
        self.assertEqual(db["next_task_id"], before["next_task_id"])

    def test_delete_habit_with_logs_returns_the_same_logs(self):
        db = fresh_db()
        habit_service.add(db, "Read")
        habit_service.log(db, 1, today="2026-11-20")

        removed = habit_service.delete(db, 1)

        self.assertEqual(removed, {"id": 1, "name": "Read",
                                   "logs": ["2026-11-20"]})
        self.assertEqual(db["habits"], [])
        self.assertEqual(db["next_habit_id"], 2)


class BoundaryTests(HabitServiceTestCase):
    def test_task_sections_are_untouched_on_success_and_failure(self):
        db = populated_db()
        before_tasks = copy.deepcopy(db["tasks"])
        before_task_id = db["next_task_id"]

        habit_service.add(db, "New")
        habit_service.log(db, 1, today="2026-11-21")
        habit_service.delete(db, 2)
        for operation, args in (
            (habit_service.add, ("   ",)),
            (habit_service.log, (None,)),
            (habit_service.log, (1, "bad")),
            (habit_service.delete, (True,)),
            (habit_service.delete, (42,)),
        ):
            with self.assertRaises(ValueError):
                operation(db, *args)

        self.assertEqual(db["tasks"], before_tasks)
        self.assertEqual(db["next_task_id"], before_task_id)


class PurityTests(HabitServiceTestCase):
    def test_operations_do_not_print_anything(self):
        db = populated_db()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            habit_service.add(db, "New")
            habit_service.list_habits(db)
            habit_service.log(db, 1, today="2026-11-21")
            habit_service.delete(db, 2)
            for operation, args in (
                (habit_service.add, ("",)),
                (habit_service.log, (None,)),
                (habit_service.log, (1, "2026-13-40")),
                (habit_service.log, (1, "2026-11-20")),
                (habit_service.delete, (False,)),
                (habit_service.delete, (99,)),
            ):
                with self.assertRaises(ValueError):
                    operation(db, *args)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_service_never_opens_files_or_imports_storage_or_cli(self):
        self.assertFalse(hasattr(habit_service, "storage"))
        self.assertFalse(hasattr(habit_service, "argparse"))
        db = fresh_db()

        with mock.patch("builtins.open") as mocked_open:
            habit_service.add(db, "Read")
            habit_service.list_habits(db)
            habit_service.log(db, 1, today="2026-11-20")
            habit_service.delete(db, 1)

        mocked_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
