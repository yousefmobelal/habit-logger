"""Tests for services.summary_service."""

import copy
import inspect
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from unittest import mock

from services import summary_service

EXPECTED_KEYS = {
    "total_tasks",
    "pending_tasks",
    "completed_tasks",
    "total_habits",
    "habits_logged_today",
}
TODAY = "2026-11-21"


def fresh_db():
    """Return a new empty in-memory database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def mixed_db():
    """Return 3 tasks (2 complete) and 3 habits (2 logged on TODAY)."""
    return {
        "tasks": [
            {"id": 1, "name": "Study", "completed": True},
            {"id": 2, "name": "Exercise", "completed": False},
            {"id": 3, "name": "Read", "completed": True},
        ],
        "habits": [
            {"id": 1, "name": "Read", "logs": ["2026-11-20", TODAY]},
            {"id": 2, "name": "Meditate", "logs": ["2026-11-19"]},
            {"id": 3, "name": "Write", "logs": [TODAY, TODAY]},
        ],
        "next_task_id": 4,
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


class SummaryTestCase(unittest.TestCase):
    """Shared assertions for the summary service."""

    def assert_counts(self, result, expected):
        self.assertIs(type(result), dict)
        self.assertEqual(set(result), EXPECTED_KEYS)
        for key in EXPECTED_KEYS:
            self.assertIs(type(result[key]), int, key)
        self.assertEqual(result, expected)


class ApiTests(SummaryTestCase):
    def test_get_summary_has_the_exact_signature(self):
        signature = inspect.signature(summary_service.get_summary)

        self.assertEqual(str(signature), "(db, today=None) -> dict")
        self.assertTrue(callable(summary_service.get_summary))

    def test_callable_with_one_or_two_positional_arguments(self):
        db = fresh_db()
        expected = {
            "total_tasks": 0,
            "pending_tasks": 0,
            "completed_tasks": 0,
            "total_habits": 0,
            "habits_logged_today": 0,
        }

        self.assert_counts(summary_service.get_summary(db), expected)
        self.assert_counts(summary_service.get_summary(db, TODAY), expected)

    def test_module_does_not_reference_storage_or_cli(self):
        source = inspect.getsource(summary_service).lower()

        self.assertNotIn("storage", source)
        self.assertNotIn("argparse", source)
        self.assertFalse(hasattr(summary_service, "storage"))
        self.assertFalse(hasattr(summary_service, "argparse"))


class EmptyDatabaseTests(SummaryTestCase):
    def test_empty_db_returns_five_zero_counts(self):
        db = fresh_db()
        expected = {
            "total_tasks": 0,
            "pending_tasks": 0,
            "completed_tasks": 0,
            "total_habits": 0,
            "habits_logged_today": 0,
        }

        self.assert_counts(summary_service.get_summary(db, TODAY), expected)
        self.assertEqual(db, fresh_db())


class MixedDatasetTests(SummaryTestCase):
    EXPECTED = {
        "total_tasks": 3,
        "pending_tasks": 1,
        "completed_tasks": 2,
        "total_habits": 3,
        "habits_logged_today": 2,
    }

    def test_mixed_dataset_returns_the_exact_expected_result(self):
        self.assert_counts(
            summary_service.get_summary(mixed_db(), TODAY), self.EXPECTED
        )

    def test_result_is_a_plain_dict_with_only_the_five_keys(self):
        result = summary_service.get_summary(mixed_db(), TODAY)

        self.assertIs(type(result), dict)
        self.assertEqual(set(result), EXPECTED_KEYS)
        self.assertEqual(len(result), 5)

    def test_every_value_is_a_plain_int(self):
        result = summary_service.get_summary(mixed_db(), TODAY)

        for key in EXPECTED_KEYS:
            with self.subTest(key=key):
                self.assertIs(type(result[key]), int)


class CompletedValueTests(SummaryTestCase):
    def test_only_exact_true_counts_as_completed(self):
        values = (True, True, False, 1, 0, "True", "", None, [], {}, 1.0)
        db = fresh_db()
        for task_id, value in enumerate(values, start=1):
            db["tasks"].append(
                {"id": task_id, "name": f"Task {task_id}", "completed": value}
            )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["total_tasks"], len(values))
        self.assertEqual(result["completed_tasks"], 2)
        self.assertEqual(result["pending_tasks"], len(values) - 2)

    def test_missing_completed_key_counts_as_pending(self):
        db = fresh_db()
        db["tasks"].extend(
            [
                {"id": 1, "name": "No flag"},
                {"id": 2, "name": "Flagged", "completed": True},
            ]
        )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["completed_tasks"], 1)
        self.assertEqual(result["pending_tasks"], 1)

    def test_pending_plus_completed_always_equals_total(self):
        for db in (fresh_db(), mixed_db()):
            with self.subTest(db=db):
                result = summary_service.get_summary(db, TODAY)
                self.assertEqual(
                    result["pending_tasks"] + result["completed_tasks"],
                    result["total_tasks"],
                )


class CountingTests(SummaryTestCase):
    def test_totals_use_list_lengths_with_id_gaps(self):
        db = {
            "tasks": [
                {"id": 2, "name": "A", "completed": True},
                {"id": 5, "name": "B", "completed": False},
                {"id": 9, "name": "C", "completed": True},
            ],
            "habits": [
                {"id": 3, "name": "X", "logs": []},
                {"id": 8, "name": "Y", "logs": [TODAY]},
            ],
            "next_task_id": 10,
            "next_habit_id": 12,
        }

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["total_tasks"], 3)
        self.assertEqual(result["total_habits"], 2)
        self.assertEqual(result["completed_tasks"], 2)
        self.assertEqual(result["habits_logged_today"], 1)

    def test_duplicate_names_are_counted_as_separate_records(self):
        db = fresh_db()
        for task_id in (1, 2):
            db["tasks"].append(
                {"id": task_id, "name": "Same", "completed": task_id == 1}
            )
        for habit_id in (1, 2):
            db["habits"].append(
                {"id": habit_id, "name": "Same", "logs": [TODAY]}
            )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["total_tasks"], 2)
        self.assertEqual(result["total_habits"], 2)
        self.assertEqual(result["habits_logged_today"], 2)

    def test_extra_top_level_keys_do_not_change_counts_or_keys(self):
        db = mixed_db()
        db["unrelated"] = {"anything": [1, 2, 3]}
        db["next_task_id"] = 999
        db["next_habit_id"] = 999

        self.assert_counts(
            summary_service.get_summary(db, TODAY), MixedDatasetTests.EXPECTED
        )


class LogMatchingTests(SummaryTestCase):
    def test_today_plus_other_dates_counts_once(self):
        db = fresh_db()
        db["habits"].append(
            {
                "id": 1,
                "name": "Mixed",
                "logs": ["2026-11-19", TODAY, "2026-11-22"],
            }
        )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["habits_logged_today"], 1)

    def test_duplicate_today_entries_count_once(self):
        db = fresh_db()
        db["habits"].append(
            {"id": 1, "name": "Dup", "logs": [TODAY, TODAY, TODAY]}
        )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["habits_logged_today"], 1)

    def test_non_matching_logs_do_not_count(self):
        db = fresh_db()
        db["habits"].append(
            {"id": 1, "name": "Other", "logs": ["2026-11-20"] * 50}
        )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["habits_logged_today"], 0)

    def test_only_exact_string_equality_matches(self):
        near_misses = (
            "2026-11-2",
            "2026-11-21T00:00:00",
            " 2026-11-21",
            "2026-11-21 ",
            None,
            20261121,
            1,
            True,
            1.5,
            [],
            {},
            (),
        )
        db = fresh_db()
        db["habits"].append(
            {"id": 1, "name": "Near", "logs": list(near_misses)}
        )
        db["habits"].append(
            {"id": 2, "name": "Exact", "logs": list(near_misses) + [TODAY]}
        )

        result = summary_service.get_summary(db, TODAY)

        self.assertEqual(result["total_habits"], 2)
        self.assertEqual(result["habits_logged_today"], 1)


class TodayArgumentTests(SummaryTestCase):
    def test_explicit_today_controls_the_count(self):
        result = summary_service.get_summary(mixed_db(), TODAY)

        self.assertEqual(result["habits_logged_today"], 2)

    def test_explicit_today_is_independent_of_the_real_date(self):
        db = fresh_db()
        db["habits"].append({"id": 1, "name": "Old", "logs": ["2020-01-01"]})

        with mock.patch.object(summary_service, "date", FixedTodayDate(TODAY)):
            result = summary_service.get_summary(db, "2020-01-01")

        self.assertEqual(result["habits_logged_today"], 1)

    def test_explicit_none_uses_the_default_today(self):
        db = fresh_db()
        db["habits"].append({"id": 1, "name": "Today", "logs": [TODAY]})

        with mock.patch.object(summary_service, "date", FixedTodayDate(TODAY)):
            result = summary_service.get_summary(db, None)

        self.assertEqual(result["habits_logged_today"], 1)

    def test_default_today_is_evaluated_at_call_time(self):
        db = fresh_db()
        db["habits"].extend(
            [
                {"id": 1, "name": "Earlier", "logs": ["2026-11-20", TODAY]},
                {"id": 2, "name": "Latest", "logs": [TODAY]},
            ]
        )

        with mock.patch.object(summary_service, "date") as mocked_date:
            mocked_date.today.return_value.isoformat.return_value = "2026-11-20"
            first = summary_service.get_summary(db)
        mocked_date.today.assert_called_once_with()

        with mock.patch.object(
            summary_service, "date", FixedTodayDate(TODAY)
        ):
            second = summary_service.get_summary(db)

        self.assertEqual(first["habits_logged_today"], 1)
        self.assertEqual(second["habits_logged_today"], 2)
        self.assertNotEqual(
            first["habits_logged_today"], second["habits_logged_today"]
        )

    def test_default_today_matches_the_real_local_date_when_unpatched(self):
        local_today = date.today().isoformat()
        db = fresh_db()
        db["habits"].append({"id": 1, "name": "Now", "logs": [local_today]})

        result = summary_service.get_summary(db)

        self.assertEqual(result["habits_logged_today"], 1)


class InvalidTodayTests(SummaryTestCase):
    INVALID_VALUES = (
        123,
        0,
        "",
        "2026-13-40",
        "2026-2-03",
        " 2026-11-21 ",
        "2026-11-21\n",
        "2026-11-21T00:00:00",
        "21-11-2026",
        date(2026, 11, 21),
        datetime(2026, 11, 21),
        1.5,
        True,
        False,
        [],
        {},
        (),
    )

    def test_invalid_today_values_raise_clear_value_errors(self):
        for value in self.INVALID_VALUES:
            with self.subTest(today=value):
                db = mixed_db()
                before = copy.deepcopy(db)

                with self.assertRaises(ValueError) as caught:
                    summary_service.get_summary(db, value)

                message = str(caught.exception)
                self.assertIn("date", message.lower())
                self.assertIn("YYYY-MM-DD", message)
                self.assertIn(repr(value), message)
                self.assertEqual(db, before)

    def test_valid_boundary_dates_are_accepted(self):
        for value in ("2024-02-29", "2000-01-01", "9999-12-31"):
            with self.subTest(today=value):
                db = fresh_db()
                db["habits"].append({"id": 1, "name": "Leap", "logs": [value]})

                result = summary_service.get_summary(db, value)

                self.assertEqual(result["habits_logged_today"], 1)


class ReadOnlyAndPurityTests(SummaryTestCase):
    def test_db_is_unchanged_after_successful_calls(self):
        for today_arg in (TODAY, None):
            with self.subTest(today=today_arg):
                db = mixed_db()
                before = copy.deepcopy(db)

                summary_service.get_summary(db, today_arg)

                self.assertEqual(db, before)

    def test_result_can_be_mutated_without_touching_the_db(self):
        db = mixed_db()
        before = copy.deepcopy(db)

        result = summary_service.get_summary(db, TODAY)
        result["total_tasks"] = 99
        result["new_key"] = "unexpected"

        self.assertEqual(db, before)
        self.assertNotIn("new_key", summary_service.get_summary(db, TODAY))

    def test_calls_produce_no_stdout_or_stderr(self):
        db = mixed_db()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.object(summary_service, "date", FixedTodayDate(TODAY)):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                summary_service.get_summary(db)
                summary_service.get_summary(db, TODAY)
                with self.assertRaises(ValueError):
                    summary_service.get_summary(db, "not-a-date")

        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_calls_open_no_files(self):
        db = mixed_db()

        with mock.patch("builtins.open") as mocked_open:
            summary_service.get_summary(db, TODAY)
            with self.assertRaises(ValueError):
                summary_service.get_summary(db, 123)

        mocked_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
