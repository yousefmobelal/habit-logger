"""Tests for services.task_service."""

import copy
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from services import task_service


def fresh_db():
    """Return a new empty in-memory database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def populated_db():
    """Return a database containing tasks, a habit, and advanced id counters."""
    return {
        "tasks": [
            {"id": 1, "name": "Study", "completed": False},
            {"id": 2, "name": "Exercise", "completed": True},
        ],
        "habits": [
            {"id": 1, "name": "Read", "logs": ["2026-11-21"]},
        ],
        "next_task_id": 3,
        "next_habit_id": 2,
    }


class TaskServiceTestCase(unittest.TestCase):
    """Shared assertions for rejected service calls."""

    def assert_rejected(self, operation, db, argument, field, value_fragment):
        before = copy.deepcopy(db)
        with self.assertRaises(ValueError) as caught:
            operation(db, argument)
        message = str(caught.exception)
        self.assertIn(field, message.lower())
        self.assertIn(value_fragment, message)
        self.assertEqual(db, before)


class TaskServiceApiTests(TaskServiceTestCase):
    def test_required_functions_are_module_level_and_callable(self):
        for name in ("add", "list_tasks", "complete", "uncomplete", "delete"):
            with self.subTest(function=name):
                self.assertTrue(callable(getattr(task_service, name)))


class AddTaskTests(TaskServiceTestCase):
    def test_add_to_fresh_db_returns_the_stored_task(self):
        db = fresh_db()
        result = task_service.add(db, "Study")

        self.assertIs(result, db["tasks"][-1])
        self.assertEqual(result, {"id": 1, "name": "Study", "completed": False})
        self.assertEqual(db["tasks"], [result])
        self.assertEqual(db["next_task_id"], 2)
        self.assertEqual(db["habits"], [])
        self.assertEqual(db["next_habit_id"], 1)

    def test_second_add_gets_next_id(self):
        db = fresh_db()
        first = task_service.add(db, "Study")
        second = task_service.add(db, "Exercise")

        self.assertEqual((first["id"], second["id"]), (1, 2))
        self.assertIs(second, db["tasks"][-1])
        self.assertEqual(db["next_task_id"], 3)

    def test_delete_then_add_does_not_reuse_id(self):
        db = fresh_db()
        task_service.add(db, "One")
        task_service.add(db, "Two")
        task_service.delete(db, 1)

        third = task_service.add(db, "Three")
        self.assertEqual(third["id"], 3)
        self.assertEqual([task["id"] for task in db["tasks"]], [2, 3])
        self.assertEqual(db["next_task_id"], 4)

    def test_delete_highest_id_then_add_does_not_reuse_id(self):
        db = fresh_db()
        task_service.add(db, "One")
        task_service.add(db, "Two")
        task_service.delete(db, 2)

        self.assertEqual(task_service.add(db, "Three")["id"], 3)
        self.assertEqual(db["next_task_id"], 4)

    def test_add_preserves_name_exactly_and_allows_duplicates(self):
        db = fresh_db()
        first = task_service.add(db, " Study ")
        second = task_service.add(db, " Study ")

        self.assertEqual(first["name"], " Study ")
        self.assertEqual(second["name"], " Study ")
        self.assertIsNot(first, second)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual([task["id"] for task in db["tasks"]], [1, 2])

    def test_add_stores_unicode_and_punctuation_unchanged(self):
        db = fresh_db()
        name = "Réviser — écrire: oui"

        self.assertEqual(task_service.add(db, name)["name"], name)

    def test_invalid_names_raise_and_leave_db_unchanged(self):
        invalid_names = ("", "   ", "\t\n", None, 123, [], True, False, 1.5, {}, ())
        for name in invalid_names:
            with self.subTest(name=name):
                db = populated_db()
                self.assert_rejected(
                    task_service.add, db, name, "name", "non-empty"
                )

    def test_failed_add_does_not_consume_an_id(self):
        db = fresh_db()
        with self.assertRaises(ValueError):
            task_service.add(db, "   ")

        self.assertEqual(task_service.add(db, "Valid")["id"], 1)
        self.assertEqual(db["next_task_id"], 2)


class InvalidIdTests(TaskServiceTestCase):
    OPERATIONS = (task_service.complete, task_service.uncomplete, task_service.delete)

    def test_invalid_ids_raise_and_leave_db_unchanged(self):
        invalid_ids = (None, "1", 1.0, 1.5, 0, -1, True, False)
        for operation in self.OPERATIONS:
            for task_id in invalid_ids:
                with self.subTest(operation=operation.__name__, task_id=task_id):
                    db = populated_db()
                    self.assert_rejected(
                        operation, db, task_id, "id", repr(task_id)
                    )

    def test_int_subclass_is_not_a_plain_int(self):
        class TaskId(int):
            pass

        for operation in self.OPERATIONS:
            with self.subTest(operation=operation.__name__):
                db = populated_db()
                self.assert_rejected(
                    operation, db, TaskId(1), "id", "positive integer"
                )

    def test_unknown_ids_raise_and_leave_db_unchanged(self):
        for operation in self.OPERATIONS:
            with self.subTest(operation=operation.__name__):
                db = populated_db()
                self.assert_rejected(operation, db, 42, "id", "42")

    def test_unknown_id_on_empty_db_raises_and_leaves_db_unchanged(self):
        for operation in self.OPERATIONS:
            with self.subTest(operation=operation.__name__):
                db = fresh_db()
                self.assert_rejected(operation, db, 42, "id", "42")


class CompletionTests(TaskServiceTestCase):
    def test_complete_sets_only_completed_and_returns_same_task(self):
        db = populated_db()
        before = copy.deepcopy(db)
        target = db["tasks"][0]

        result = task_service.complete(db, 1)

        self.assertIs(result, target)
        self.assertIs(result, db["tasks"][0])
        expected = copy.deepcopy(before)
        expected["tasks"][0]["completed"] = True
        self.assertEqual(db, expected)

    def test_uncomplete_sets_only_completed_and_returns_same_task(self):
        db = populated_db()
        before = copy.deepcopy(db)
        target = db["tasks"][1]

        result = task_service.uncomplete(db, 2)

        self.assertIs(result, target)
        self.assertIs(result, db["tasks"][1])
        expected = copy.deepcopy(before)
        expected["tasks"][1]["completed"] = False
        self.assertEqual(db, expected)

    def test_complete_is_idempotent(self):
        db = populated_db()
        task_service.complete(db, 1)
        snapshot = copy.deepcopy(db)

        for _ in range(2):
            result = task_service.complete(db, 1)
            self.assertIs(result, db["tasks"][0])
            self.assertEqual(db, snapshot)

    def test_uncomplete_is_idempotent(self):
        db = fresh_db()
        task_service.add(db, "Study")
        task_service.uncomplete(db, 1)
        snapshot = copy.deepcopy(db)

        for _ in range(2):
            result = task_service.uncomplete(db, 1)
            self.assertIs(result, db["tasks"][0])
            self.assertEqual(db, snapshot)

    def test_complete_uncomplete_complete_round_trip(self):
        db = fresh_db()
        task_service.add(db, "Study")

        self.assertTrue(task_service.complete(db, 1)["completed"])
        self.assertFalse(task_service.uncomplete(db, 1)["completed"])
        self.assertTrue(task_service.complete(db, 1)["completed"])
        self.assertEqual(
            db["tasks"],
            [{"id": 1, "name": "Study", "completed": True}],
        )


class ListTasksTests(TaskServiceTestCase):
    def test_list_tasks_returns_empty_list_for_empty_db(self):
        db = fresh_db()

        self.assertEqual(task_service.list_tasks(db), [])
        self.assertEqual(db, fresh_db())

    def test_list_tasks_preserves_insertion_order_and_flags(self):
        db = fresh_db()
        task_service.add(db, "First")
        task_service.add(db, "Second")
        task_service.add(db, "Third")
        task_service.complete(db, 2)

        tasks = task_service.list_tasks(db)

        self.assertEqual(tasks, db["tasks"])
        self.assertEqual(
            [task["name"] for task in tasks],
            ["First", "Second", "Third"],
        )
        self.assertEqual(
            [task["completed"] for task in tasks],
            [False, True, False],
        )

    def test_list_tasks_does_not_mutate_db(self):
        db = populated_db()
        before = copy.deepcopy(db)

        tasks = task_service.list_tasks(db)
        self.assertEqual(db, before)
        tasks.reverse()
        tasks.clear()
        self.assertEqual(db, before)


class DeleteTaskTests(TaskServiceTestCase):
    def test_delete_removes_only_target_and_returns_removed_task(self):
        db = {
            "tasks": [
                {"id": 1, "name": "A", "completed": False},
                {"id": 2, "name": "B", "completed": True},
                {"id": 3, "name": "C", "completed": False},
            ],
            "habits": [{"id": 4, "name": "Habit", "logs": []}],
            "next_task_id": 5,
            "next_habit_id": 6,
        }
        before = copy.deepcopy(db)
        target = db["tasks"][1]

        removed = task_service.delete(db, 2)

        self.assertIs(removed, target)
        self.assertEqual(removed, before["tasks"][1])
        expected = copy.deepcopy(before)
        del expected["tasks"][1]
        self.assertEqual(db, expected)
        self.assertEqual(db["next_task_id"], 5)
        self.assertEqual(db["next_habit_id"], 6)


class PurityTests(TaskServiceTestCase):
    def test_operations_do_not_print_or_touch_habits(self):
        db = populated_db()
        before_habits = copy.deepcopy(db["habits"])
        stdout = io.StringIO()
        stderr = io.StringIO()

        with redirect_stdout(stdout), redirect_stderr(stderr):
            task_service.add(db, "New")
            task_service.list_tasks(db)
            task_service.complete(db, 1)
            task_service.uncomplete(db, 2)
            task_service.delete(db, 2)
            for operation, argument in (
                (task_service.add, "   "),
                (task_service.complete, None),
                (task_service.uncomplete, 42),
                (task_service.delete, True),
            ):
                with self.assertRaises(ValueError):
                    operation(db, argument)

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(db["habits"], before_habits)
        self.assertEqual(db["next_habit_id"], 2)

    def test_service_never_opens_files_or_imports_storage(self):
        self.assertFalse(hasattr(task_service, "storage"))
        db = fresh_db()
        with mock.patch("builtins.open") as mocked_open:
            task_service.add(db, "Study")
            task_service.list_tasks(db)
            task_service.complete(db, 1)
            task_service.uncomplete(db, 1)
            task_service.delete(db, 1)
        mocked_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
