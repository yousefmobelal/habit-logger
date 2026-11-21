# AGENTS.md

Instructions for agents working in this repository.

## Project

Command-based CLI for one-time tasks and daily habits. The MVP scope is in `_docs/outdated/plan.md`; the backlog is in [GitHub Issues](https://github.com/yousefmobelal/habit-logger/issues). Files under `_docs/outdated/` are read-only archives.

## Tech stack

- Python 3, standard library only. No third-party dependencies, build step, or packaging in the MVP.
- `argparse` for commands, `unittest` for tests, one JSON file for storage: `data/db.json` (override with `HABIT_LOGGER_DB`).
- Habit logs use the local date (`date.today().isoformat()`) as `YYYY-MM-DD` strings.

## Commands

Run from the project root:

- `python -m unittest discover -s tests` — full test suite.
- `python -m unittest tests.test_task_service` — a single test module.
- `python main.py task|habit|summary ...` — run the CLI.

No install, lint, or format command is configured.

## Layout and boundaries

```
main.py                  root parser and dispatch
commands/                argparse subcommands and user-facing output
services/                business logic on an in-memory db dict
storage/json_storage.py  all JSON file I/O
data/db.json             runtime data; do not commit
tests/                   unittest tests
```

- Keep file I/O in `storage/`, business logic in `services/`, and argument parsing and printing in `commands/`.
- Services mutate the `db` dict in place and raise `ValueError` with clear messages for invalid input. Commands load through `storage`, save after success, print errors to stderr, and return 0 on success / 1 on error.
- Data shape: `{"tasks": [{"id", "name", "completed"}], "habits": [{"id", "name", "logs": [...]}], "next_task_id", "next_habit_id"}`. IDs are incremental, unique per module, and never reused after deletion.
- A habit may be logged only once per local calendar day; reject repeats with a helpful message.
- A missing JSON file means an empty database. Corrupt JSON must produce a clear error and must never be silently overwritten.

## Formatting

- Follow PEP 8: 4 spaces, no tabs, lines under 100 characters (88 preferred).
- Use `snake_case` for functions and variables, `PascalCase` for classes.
- End files with a newline; no trailing whitespace. Match existing style when editing.

## Working guidelines

- Work on one open issue at a time and keep changes scoped to it.
- Do not add out-of-scope features: priorities, due dates, tags, streaks, history views, filtering, interactive menus, other databases, or new dependencies.
- Add or update tests for every behavior change. Use `tempfile` paths or patched `HABIT_LOGGER_DB`/`DB_PATH`; never touch a real `data/db.json`.
- Run `python -m unittest discover -s tests` before finishing and report any failures.
- Keep messages friendly and specific; empty lists print "No tasks yet." or "No habits yet.".
- Commit small, focused changes with short imperative messages.
