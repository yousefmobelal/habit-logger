# Habit Logger (MVP)

## Description/setup

An MVP command-based CLI for one-time tasks and daily habits. Requires Python 3 and only the standard library: no third-party dependencies, install step, build step, or packaging. Run all commands from the project root as `python main.py ...`.

## Command reference

Commands follow the [archived full MVP reference](_docs/outdated/plan.md#11-full-mvp-command-reference). On an empty database, `task list` prints `No tasks yet.` and `habit list` prints `No habits yet.`

Tasks (sample stdout; `task list` is shown before and after completion):
```text
python main.py task add "Study Python"
python main.py task list
python main.py task complete 1
python main.py task uncomplete 1
python main.py task delete 1
```
`Added task 1: Study Python` after add; `task list` prints `1: Study Python [pending]` before completion and `1: Study Python [completed]` after completion; complete prints `Completed task 1: Study Python`, uncomplete prints `Uncompleted task 1: Study Python`, delete prints `Deleted task 1: Study Python`.

Habits (stdout after each command; `YYYY-MM-DD` is the local date):
```text
python main.py habit add "Read 30 minutes"
python main.py habit list
python main.py habit log 1
python main.py habit delete 1
```
`Added habit 1: Read 30 minutes` after add; `1: Read 30 minutes` after list; `Logged habit 1: Read 30 minutes on YYYY-MM-DD` after log; `Deleted habit 1: Read 30 minutes` after delete.

Summary (five stdout lines, in order; `N` is the current count):
```text
python main.py summary
```
`Total tasks: N`; `Pending tasks: N`; `Completed tasks: N`; `Total habits: N`; `Habits logged today: N`.

## Storage/rules

- Data lives in one JSON file, `data/db.json`, created on first write; a missing file means an empty database, and deleting the file resets all data. Override with `HABIT_LOGGER_DB` before running, e.g. `HABIT_LOGGER_DB=./my-data.json python main.py task list`; the default remains `data/db.json` when unset.
- IDs are numeric, incremental, and unique per module: task and habit counters start at 1, are separate, and are never reused after deletion.
- A habit may be logged only once per local calendar day; logs are `YYYY-MM-DD` strings. A second log that day prints `Habit 'Read 30 minutes' is already logged on YYYY-MM-DD.` to stderr and exits 1.
- Successful commands print results to stdout and exit 0; `task list`, `habit list`, and `summary` do not modify data.

## Errors/exit codes

Expected failures print a specific message to stderr and exit 1: blank names (`Task name must be a non-empty string.` / `Habit name must be a non-empty string.`), non-numeric IDs (`invalid literal for int() with base 10: 'abc'`), non-positive IDs (`Task id must be a positive integer, got 0.` / `Habit id must be a positive integer, got 0.`), unknown IDs (`No task found with id 1.` / `No habit found with id 1.`), duplicate logs (message above), and corrupt JSON (`Invalid JSON in <path>: <detail>`).
Corrupt JSON is reported but never silently overwritten. A non-numeric ID is caught by `int()` in the command layer (stderr, exit 1); a missing required argument (such as an ID) is an argparse usage error (usage to stderr, exit 2), as are unknown commands/actions. Bare `python main.py` does nothing and exits 0.

## Testing

From the project root, `python -m unittest discover -s tests` runs the full suite and must pass.

## MVP boundaries

No priorities, due dates, tags/categories, subtasks, recurring tasks, time tracking, habit frequencies/schedules, streaks, habit-history views, filtering, sorting, editing, interactive menus, other databases, third-party dependencies, install/build steps, or packaging.
