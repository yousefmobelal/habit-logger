# habit-logger

habit-logger is an MVP command-based CLI for managing one-time tasks and daily habits.

## Description and setup

- Requires Python 3.
- Uses only the Python standard library: no third-party dependencies.
- No install step, build step, or packaging; run from a checkout.
- Run every command from the project root as `python main.py ...`.

## Command reference

Examples follow the [archived full MVP command reference](_docs/outdated/plan.md#11-full-mvp-command-reference). On an empty database, `task list` prints `No tasks yet.` and `habit list` prints `No habits yet.`

**Tasks**

```text
python main.py task add "Study Python"
Added task 1: Study Python
python main.py task list
1: Study Python [pending]
python main.py task complete 1
Completed task 1: Study Python
python main.py task list
1: Study Python [completed]
python main.py task uncomplete 1
Uncompleted task 1: Study Python
python main.py task delete 1
Deleted task 1: Study Python
```

**Habits**

```text
python main.py habit add "Read 30 minutes"
Added habit 1: Read 30 minutes
python main.py habit list
1: Read 30 minutes
python main.py habit log 1
Logged habit 1: Read 30 minutes on YYYY-MM-DD
python main.py habit delete 1
Deleted habit 1: Read 30 minutes
```

`YYYY-MM-DD` is the local date when the habit is logged.

**Summary**

```text
python main.py summary
Total tasks: N
Pending tasks: N
Completed tasks: N
Total habits: N
Habits logged today: N
```

`N` is the current count for each line.

## Storage and rules

- Data lives in one JSON file at `data/db.json`. It is created on first write; a missing file means an empty database, and deleting the file resets all data.
- Override the path by setting `HABIT_LOGGER_DB` before running the CLI, for example `HABIT_LOGGER_DB=./my-data.json python main.py task list`. When unset, the default is `data/db.json`.
- IDs are numeric, incremental, and unique per module: task and habit IDs use separate counters starting at 1, and IDs are never reused after deletion.
- A habit may be logged only once per local calendar day. Logs are stored as `YYYY-MM-DD` strings. A second log on the same day prints `Habit 'Read 30 minutes' is already logged on YYYY-MM-DD.` to stderr and exits 1.
- Successful commands print their result to stdout and exit 0. `task list`, `habit list`, and `summary` do not modify data.

## Errors and exit codes

Expected failures print a specific message to stderr and exit 1:

- Blank names: `Task name must be a non-empty string.` or `Habit name must be a non-empty string.`
- Malformed IDs: non-numeric values are caught by `int()` in the command layer (for example, `invalid literal for int() with base 10: 'abc'`); numeric IDs must be positive (`Task id must be a positive integer, got 0.` or `Habit id must be a positive integer, got 0.`).
- Nonexistent IDs: `No task found with id 1.` or `No habit found with id 1.`
- Duplicate habit log: the message shown in the storage rules above.
- Corrupt JSON: `Invalid JSON in <path>: <detail>`. It is reported but never silently overwritten.

A non-numeric ID argument therefore exits 1, while a missing ID argument is an argparse usage error that prints usage to stderr and exits 2. Argparse usage errors for unknown commands or actions also print usage to stderr and exit 2. A bare `python main.py` performs no action and exits 0.

## Testing

From the project root, run `python -m unittest discover -s tests`. The full test suite must pass.

## MVP boundaries

This MVP has no priorities, due dates, tags/categories, subtasks, recurring tasks, time tracking, habit frequencies or schedules, streaks, habit-history views, filtering, sorting, editing, interactive menus, other databases, third-party dependencies, install step, build step, or packaging.
