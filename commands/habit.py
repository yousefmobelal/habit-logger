"""Argparse subcommands and user-facing output for daily habits."""

import sys

from services import habit_service
from storage import json_storage as storage


def register(subparsers):
    """Attach the habit command group and its actions to *subparsers*."""
    habit_parser = subparsers.add_parser("habit", help="Manage daily habits.")
    habit_subparsers = habit_parser.add_subparsers(dest="habit_action")

    add_parser = habit_subparsers.add_parser("add", help="Add a new habit.")
    add_parser.add_argument("name", help="Name of the habit.")
    add_parser.set_defaults(func=handle_habit_add)

    list_parser = habit_subparsers.add_parser("list", help="List all habits.")
    list_parser.set_defaults(func=handle_habit_list)

    log_parser = habit_subparsers.add_parser("log", help="Log a habit for today.")
    log_parser.add_argument("habit_id", help="Id of the habit.")
    log_parser.set_defaults(func=handle_habit_log)

    delete_parser = habit_subparsers.add_parser(
        "delete", help="Delete a habit."
    )
    delete_parser.add_argument("habit_id", help="Id of the habit.")
    delete_parser.set_defaults(func=handle_habit_delete)


def handle_habit_add(args):
    """Add a habit from *args* and report the result."""
    try:
        db = storage.load()
        habit = habit_service.add(db, args.name)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Added habit {habit['id']}: {habit['name']}")
    return 0


def handle_habit_list(args):
    """List habits from *args* without modifying the database."""
    try:
        db = storage.load()
        habits = habit_service.list_habits(db)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not habits:
        print("No habits yet.")
        return 0

    for habit in habits:
        print(f"{habit['id']}: {habit['name']}")
    return 0


def handle_habit_log(args):
    """Log the requested habit for today and report the result."""
    try:
        habit_id = int(args.habit_id)
        db = storage.load()
        habit = habit_service.log(db, habit_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(
        f"Logged habit {habit['id']}: {habit['name']} on {habit['logs'][-1]}"
    )
    return 0


def handle_habit_delete(args):
    """Delete the requested habit and report the result."""
    try:
        habit_id = int(args.habit_id)
        db = storage.load()
        habit = habit_service.delete(db, habit_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Deleted habit {habit['id']}: {habit['name']}")
    return 0
