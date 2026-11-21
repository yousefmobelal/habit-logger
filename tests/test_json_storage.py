"""Tests for storage.json_storage."""

import copy
import importlib
import json
import os
import tempfile
import unittest
from unittest import mock

from storage import json_storage

EMPTY_DB = {
    "tasks": [],
    "habits": [],
    "next_task_id": 1,
    "next_habit_id": 1,
}


class JsonStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = os.path.join(self.temp_dir.name, "db.json")

    def write_text(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def read_bytes(self):
        with open(self.path, "rb") as handle:
            return handle.read()

    def test_missing_file_returns_empty_database(self):
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(json_storage.load(self.path), EMPTY_DB)
        self.assertFalse(os.path.exists(self.path))

    def test_empty_file_raises_value_error_and_is_unchanged(self):
        self.write_text("")
        before = self.read_bytes()
        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            json_storage.load(self.path)
        self.assertEqual(self.read_bytes(), before)

    def test_corrupt_json_raises_value_error_and_is_unchanged(self):
        self.write_text('{"tasks": [}')
        before = self.read_bytes()
        with self.assertRaisesRegex(ValueError, "Invalid JSON"):
            json_storage.load(self.path)
        self.assertEqual(self.read_bytes(), before)

    def test_non_object_top_level_raises_value_error_and_is_unchanged(self):
        for content in ("[]", "null", '"text"', "42"):
            with self.subTest(content=content):
                self.write_text(content)
                before = self.read_bytes()
                with self.assertRaisesRegex(ValueError, "top level"):
                    json_storage.load(self.path)
                self.assertEqual(self.read_bytes(), before)

    def test_missing_keys_raise_value_error_and_leave_file_unchanged(self):
        for key in EMPTY_DB:
            with self.subTest(missing=key):
                payload = {k: v for k, v in EMPTY_DB.items() if k != key}
                self.write_text(json.dumps(payload))
                before = self.read_bytes()
                with self.assertRaisesRegex(ValueError, f"missing key.*{key}"):
                    json_storage.load(self.path)
                self.assertEqual(self.read_bytes(), before)

    def test_non_list_collections_raise_value_error_and_leave_file_unchanged(self):
        for key in ("tasks", "habits"):
            with self.subTest(key=key):
                payload = dict(EMPTY_DB)
                payload[key] = {"not": "a list"}
                self.write_text(json.dumps(payload))
                before = self.read_bytes()
                with self.assertRaisesRegex(ValueError, f"'{key}' must be a list"):
                    json_storage.load(self.path)
                self.assertEqual(self.read_bytes(), before)

    def test_load_returns_stored_values_unchanged(self):
        payload = {
            "tasks": [{"id": 7, "name": "Study", "completed": False}],
            "habits": [{"id": 3, "name": "Read", "logs": ["2026-11-21"]}],
            "next_task_id": 8,
            "next_habit_id": 4,
            "extra": "preserved",
        }
        self.write_text(json.dumps(payload))
        self.assertEqual(json_storage.load(self.path), payload)

    def test_save_creates_parent_directories_and_round_trips(self):
        db = {
            "tasks": [{"id": 1, "name": "Write tests", "completed": True}],
            "habits": [],
            "next_task_id": 2,
            "next_habit_id": 1,
        }
        nested_path = os.path.join(
            self.temp_dir.name, "nested", "deeper", "db.json"
        )
        self.assertFalse(os.path.exists(os.path.dirname(nested_path)))

        json_storage.save(db, nested_path)

        self.assertTrue(os.path.isfile(nested_path))
        with open(nested_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        self.assertTrue(content.startswith(json.dumps(db, indent=4)))
        self.assertIn("\n", content)
        self.assertEqual(json_storage.load(nested_path), db)

    def test_save_does_not_mutate_db_or_write_elsewhere(self):
        db = {
            "tasks": [{"id": 1, "name": "Task", "completed": False}],
            "habits": [{"id": 1, "name": "Habit", "logs": []}],
            "next_task_id": 2,
            "next_habit_id": 2,
        }
        original = copy.deepcopy(db)

        json_storage.save(db, self.path)

        self.assertEqual(db, original)
        self.assertEqual(os.listdir(self.temp_dir.name), ["db.json"])
        self.assertEqual(json_storage.load(self.path), original)


class DbPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.original_db_path = json_storage.DB_PATH
        self.original_env = os.environ.get("HABIT_LOGGER_DB")

    def tearDown(self):
        env = os.environ.copy()
        if self.original_env is None:
            env.pop("HABIT_LOGGER_DB", None)
        else:
            env["HABIT_LOGGER_DB"] = self.original_env
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(json_storage)
        self.assertEqual(json_storage.DB_PATH, self.original_db_path)

    def test_default_path_when_env_unset(self):
        env = os.environ.copy()
        env.pop("HABIT_LOGGER_DB", None)
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(json_storage)
            self.assertEqual(json_storage.DB_PATH, "data/db.json")

    def test_env_override_is_used_by_default_arguments(self):
        override = os.path.join(self.temp_dir.name, "override.json")
        with mock.patch.dict(os.environ, {"HABIT_LOGGER_DB": override}):
            importlib.reload(json_storage)
            self.assertEqual(json_storage.DB_PATH, override)

            db = json_storage.load()
            self.assertEqual(db, EMPTY_DB)
            json_storage.save(db)

        self.assertTrue(os.path.isfile(override))
        self.assertEqual(os.listdir(self.temp_dir.name), ["override.json"])


if __name__ == "__main__":
    unittest.main()
