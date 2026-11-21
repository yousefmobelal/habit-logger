"""Argparse subcommand and user-facing output for summaries."""

import sys

from services import summary_service
from storage import json_storage as storage


def register(subparsers):
    """Attach the summary command to *subparsers*."""
    summary_parser = subparsers.add_parser(
        "summary", help="Show task and habit counts."
    )
    summary_parser.set_defaults(func=handle_summary)


def handle_summary(args):
    """Print task and habit counts without changing the database."""
    try:
        db = storage.load()
        counts = summary_service.get_summary(db)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"Total tasks: {counts['total_tasks']}")
    print(f"Pending tasks: {counts['pending_tasks']}")
    print(f"Completed tasks: {counts['completed_tasks']}")
    print(f"Total habits: {counts['total_habits']}")
    print(f"Habits logged today: {counts['habits_logged_today']}")
    return 0
