"""JSON persistence for the task and habit logger."""

import json
import os

DEFAULT_DB_PATH = "data/db.json"
DB_PATH = os.environ.get("HABIT_LOGGER_DB", DEFAULT_DB_PATH)

REQUIRED_KEYS = ("tasks", "habits", "next_task_id", "next_habit_id")
LIST_KEYS = ("tasks", "habits")


def empty_db():
    """Return a new, empty database."""
    return {
        "tasks": [],
        "habits": [],
        "next_task_id": 1,
        "next_habit_id": 1,
    }


def load(path=DB_PATH):
    """Load the database from *path*, or return an empty one if absent."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read()
    except FileNotFoundError:
        return empty_db()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        db = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(db, dict):
        raise ValueError(
            f"Invalid database in {path}: top level must be a JSON object"
        )

    missing = [key for key in REQUIRED_KEYS if key not in db]
    if missing:
        raise ValueError(
            f"Invalid database in {path}: missing key(s): {', '.join(missing)}"
        )

    for key in LIST_KEYS:
        if not isinstance(db[key], list):
            raise ValueError(
                f"Invalid database in {path}: '{key}' must be a list"
            )

    return db


def save(db, path=DB_PATH):
    """Write *db* as indented JSON to *path*, creating parent directories."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(db, handle, indent=4)
        handle.write("\n")
