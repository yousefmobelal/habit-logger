"""Argparse subcommands and user-facing output for one-time tasks."""

import sys

from services import task_service
from storage import json_storage as storage


def register(subparsers):
    """Attach the task command group and its actions to *subparsers*."""
    task_parser = subparsers.add_parser("task", help="Manage one-time tasks.")
    task_subparsers = task_parser.add_subparsers(dest="task_action")

    add_parser = task_subparsers.add_parser("add", help="Add a new task.")
    add_parser.add_argument("name", help="Name of the task.")
    add_parser.set_defaults(func=handle_task_add)

    list_parser = task_subparsers.add_parser("list", help="List all tasks.")
    list_parser.set_defaults(func=handle_task_list)

    complete_parser = task_subparsers.add_parser(
        "complete", help="Mark a task complete."
    )
    complete_parser.add_argument("task_id", help="Id of the task.")
    complete_parser.set_defaults(func=handle_task_complete)

    uncomplete_parser = task_subparsers.add_parser(
        "uncomplete", help="Mark a task pending."
    )
    uncomplete_parser.add_argument("task_id", help="Id of the task.")
    uncomplete_parser.set_defaults(func=handle_task_uncomplete)

    delete_parser = task_subparsers.add_parser("delete", help="Delete a task.")
    delete_parser.add_argument("task_id", help="Id of the task.")
    delete_parser.set_defaults(func=handle_task_delete)


def handle_task_add(args):
    """Add a task from *args* and report the result."""
    try:
        db = storage.load()
        task = task_service.add(db, args.name)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Added task {task['id']}: {task['name']}")
    return 0


def handle_task_list(args):
    """List tasks from *args* without modifying the database."""
    try:
        db = storage.load()
        tasks = task_service.list_tasks(db)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    if not tasks:
        print("No tasks yet.")
        return 0

    for task in tasks:
        status = "completed" if task["completed"] else "pending"
        print(f"{task['id']}: {task['name']} [{status}]")
    return 0


def handle_task_complete(args):
    """Mark the requested task complete and report the result."""
    try:
        task_id = int(args.task_id)
        db = storage.load()
        task = task_service.complete(db, task_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Completed task {task['id']}: {task['name']}")
    return 0


def handle_task_uncomplete(args):
    """Mark the requested task pending and report the result."""
    try:
        task_id = int(args.task_id)
        db = storage.load()
        task = task_service.uncomplete(db, task_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Uncompleted task {task['id']}: {task['name']}")
    return 0


def handle_task_delete(args):
    """Delete the requested task and report the result."""
    try:
        task_id = int(args.task_id)
        db = storage.load()
        task = task_service.delete(db, task_id)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    storage.save(db)
    print(f"Deleted task {task['id']}: {task['name']}")
    return 0
