"""Pure in-memory summary counts for tasks and habits."""

import re
from datetime import date
from datetime import date as calendar_date

DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def _resolve_today(today):
    """Return *today* as a validated YYYY-MM-DD date string.

    ``None`` resolves through ``date.today()`` at call time. Explicit values
    must be strings for real calendar dates in YYYY-MM-DD form.
    """
    if today is None:
        return date.today().isoformat()
    if not isinstance(today, str) or DATE_PATTERN.fullmatch(today) is None:
        raise ValueError(
            f"Summary date must be a YYYY-MM-DD string, got {today!r}."
        )
    try:
        calendar_date.fromisoformat(today)
    except ValueError:
        raise ValueError(
            f"Summary date must be a real calendar date in YYYY-MM-DD form, "
            f"got {today!r}."
        ) from None
    return today


def get_summary(db, today=None) -> dict:
    """Return the five task and habit counts for *db* without changing it."""
    log_date = _resolve_today(today)

    tasks = db["tasks"]
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task.get("completed") is True)

    habits = db["habits"]
    total_habits = len(habits)
    habits_logged_today = sum(
        1 for habit in habits if log_date in habit.get("logs", ())
    )

    return {
        "total_tasks": total_tasks,
        "pending_tasks": total_tasks - completed_tasks,
        "completed_tasks": completed_tasks,
        "total_habits": total_habits,
        "habits_logged_today": habits_logged_today,
    }
