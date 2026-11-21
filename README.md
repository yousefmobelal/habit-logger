# Habit Logger (MVP)

## Description/setup

A command-based CLI for one-time tasks and daily habits. Requires Python 3 and only the Python standard library: no third-party dependencies, install step, build step, or packaging. Run all commands from the project root as `python main.py ...`.

## Command reference

Tasks (outputs in this order):
```bash
# Tasks
python main.py task add "Study Python"
python main.py task list
python main.py task complete 1
python main.py task uncomplete 1
python main.py task delete 1
```
`Added task 1: Study Python`; `1: Study Python [pending]`; `Completed task 1: Study Python`; `1: Study Python [completed]`; `Uncompleted task 1: Study Python`; `Deleted task 1: Study Python`. Empty list: `No tasks yet.`

Habits (outputs in this order):
```bash
# Habits
python main.py habit add "Read 30 minutes"
python main.py habit list
python main.py habit log 1
python main.py habit delete 1
```
`Added habit 1: Read 30 minutes`; `1: Read 30 minutes`; `Logged habit 1: Read 30 minutes on YYYY-MM-DD` (local date); `Deleted habit 1: Read 30 minutes`. Empty list: `No habits yet.`

Summary (five output lines in this order):
```bash
# Summary
python main.py summary
```
`Total tasks: N`, `Pending tasks: N`, `Completed tasks: N`, `Total habits: N`, `Habits logged today: N`.

## Storage/rules

Data lives in one JSON file, `data/db.json`, created on first write; a missing file means an empty database, and deleting the file resets all data. To override the path, set `HABIT_LOGGER_DB` to another file path before running, e.g. `HABIT_LOGGER_DB=data/other.json python main.py task list`; when unset, the default is still `data/db.json`. IDs are numeric, incremental, and unique per module: task and habit counters start at 1 and are never reused after deletion. A habit may be logged only once per local calendar day; logs are stored as `YYYY-MM-DD` strings. Successful commands print results to stdout and exit 0; `task list`, `habit list`, and `summary` do not modify data.

## Errors/exit codes

Expected failures (blank names, malformed or nonexistent IDs, duplicate habit log, corrupt JSON) print a specific message to stderr and exit 1; a second log prints `Habit 'Read 30 minutes' is already logged on YYYY-MM-DD.` Corrupt JSON is reported but never silently overwritten. Argparse usage errors (unknown command/action, missing required argument) print usage to stderr and exit 2, and bare `python main.py` does nothing and exits 0. A non-numeric ID argument is caught by `int()` in the command layer (stderr, exit 1); a missing ID argument is an argparse usage error (exit 2).

## Testing

From the project root, `python -m unittest discover -s tests` runs the full suite and must pass.

## MVP boundaries

MVP only: no priorities, due dates, tags/categories, subtasks, recurring tasks, time tracking, habit frequencies/schedules, streaks, habit-history views, filtering, sorting, editing, interactive menus, other databases, or packaging.
