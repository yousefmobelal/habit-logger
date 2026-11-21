"""Pure in-memory business logic for daily habits."""

import re
from datetime import date
from datetime import date as calendar_date

NAME_ERROR = "Habit name must be a non-empty string."
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _validate_name(name):
    """Raise a ValueError unless *name* is a non-blank string."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(NAME_ERROR)


def _validate_habit_id(habit_id):
    """Raise a ValueError unless *habit_id* is a plain positive int."""
    if type(habit_id) is not int or habit_id <= 0:
        raise ValueError(f"Habit id must be a positive integer, got {habit_id!r}.")


def _habit_index(db, habit_id):
    """Return the index of the habit with *habit_id* or raise a ValueError."""
    for index, habit in enumerate(db["habits"]):
        if habit["id"] == habit_id:
            return index
    raise ValueError(f"No habit found with id {habit_id}.")


def _validate_log_date(today):
    """Return the date string to log, resolving None through date.today()."""
    if today is None:
        return date.today().isoformat()
    if not isinstance(today, str) or DATE_PATTERN.fullmatch(today) is None:
        raise ValueError(f"Log date must be a YYYY-MM-DD string, got {today!r}.")
    try:
        calendar_date.fromisoformat(today)
    except ValueError:
        raise ValueError(
            f"Log date must be a real calendar date, got {today!r}."
        ) from None
    return today


def add(db, name):
    """Append a new habit named *name* and return the stored habit dict."""
    _validate_name(name)
    habit = {
        "id": db["next_habit_id"],
        "name": name,
        "logs": [],
    }
    db["habits"].append(habit)
    db["next_habit_id"] += 1
    return habit


def list_habits(db):
    """Return a shallow copy of the habit list in insertion order."""
    return list(db["habits"])


def log(db, habit_id, today=None):
    """Log *habit_id* for *today* (default: local today) and return its dict."""
    _validate_habit_id(habit_id)
    log_date = _validate_log_date(today)
    habit = db["habits"][_habit_index(db, habit_id)]
    if log_date in habit["logs"]:
        raise ValueError(
            f"Habit {habit['name']!r} is already logged on {log_date}."
        )
    habit["logs"].append(log_date)
    return habit


def delete(db, habit_id):
    """Remove and return the stored habit dict with *habit_id*."""
    _validate_habit_id(habit_id)
    return db["habits"].pop(_habit_index(db, habit_id))
