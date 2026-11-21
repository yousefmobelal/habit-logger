# Backlog — CLI Task & Habit Logger (MVP)

These tasks implement the MVP described in `_docs/plan.md`. Each task is designed to be completed in one session and to stand on its own.

## Shared conventions (apply to every task)

- Python 3, standard library only. Tests use `unittest` and live in `tests/`; run them from the project root with `python -m unittest discover -s tests`.
- The app is invoked as `python main.py ...` and uses `argparse`.
- All data lives in one JSON file, `data/db.json`, with this in-memory shape:

  ```json
  {
    "tasks": [{"id": 1, "name": "Study", "completed": false}],
    "habits": [{"id": 1, "name": "Read", "logs": ["2026-11-21"]}],
    "next_task_id": 2,
    "next_habit_id": 2
  }
  ```

- IDs are positive integers, unique within each module, and never reused after deletion; `next_task_id` and `next_habit_id` hold the next values. Habit log dates are local `YYYY-MM-DD` strings from `date.today().isoformat()`.
- `storage/json_storage.py` exposes `DB_PATH` (from the `HABIT_LOGGER_DB` environment variable if set, otherwise `data/db.json`), `load(path=DB_PATH) -> dict`, and `save(db, path=DB_PATH)`. `load` returns an empty database when the file is missing and raises `ValueError` with a clear message for corrupt JSON or an invalid structure; `save` creates parent directories and writes indented JSON. Tests pass a `tempfile` path or patch `DB_PATH`/the environment variable.
- Services in `services/` take the `db` dict, mutate it in place, and return the affected record, list, or counts. They raise `ValueError` with clear messages for empty names, malformed IDs, and unknown IDs, and never touch the filesystem.
- Command modules in `commands/` each expose `register(subparsers)` (defines its parser and sets the handler with `set_defaults(func=...)`) and handler functions `handle_*(args) -> int`. Handlers load through `storage`, call a service, save through `storage`, print user-facing output, return 0 on success, and print an error to stderr with return code 1 when a `ValueError` is raised. Empty lists print a friendly "No tasks yet." / "No habits yet." message.
- `main.py` builds the root parser, calls `register(subparsers)` on each command module, and exits with `args.func(args)`.

## Tasks

## 1. Bootstrap the project with a passing test
Goal: Establish a minimal Python project skeleton with a green test suite before any feature work.
Description: Create `main.py` with a minimal argparse entry point, the `commands/`, `services/`, `storage/`, and `tests/` directories with `__init__.py` files as needed, and a `data/.gitkeep`. Add `tests/test_smoke.py` with one trivial passing assertion and confirm `python -m unittest discover -s tests` succeeds from the project root.

## 2. Build the JSON storage layer
Goal: Persist and load the application database from `data/db.json` with safe handling of missing and corrupt files.
Description: Implement `storage/json_storage.py` with `DB_PATH`, `load`, and `save` following the shared conventions above, including creating parent directories on save and returning an empty database when the file is missing. Add `tests/test_json_storage.py` using `tempfile` to cover a round trip, a missing file, and corrupt JSON raising a clear `ValueError` without overwriting the file.

## 3. Implement the task service
Goal: Provide in-memory task operations for adding, listing, completing, uncompleting, and deleting tasks.
Description: Implement `services/task_service.py` with `add`, `list_tasks`, `complete`, `uncomplete`, and `delete` as described in the shared conventions, assigning IDs from `next_task_id` and rejecting empty names or invalid/unknown IDs with clear `ValueError` messages. Keep the service free of file I/O; it only mutates the `db` dict it receives. Add `tests/test_task_service.py` covering every operation plus the validation cases.

## 4. Implement the habit service
Goal: Provide in-memory habit operations with the once-per-day logging rule.
Description: Implement `services/habit_service.py` with `add`, `list_habits`, `log` (accepting an optional `today` date string for tests, defaulting to `date.today().isoformat()`), and `delete`, using the shared conventions for data shape and errors. `log` must reject a second completion for the same habit on the same date with a helpful message and must never alter other logged dates. Add `tests/test_habit_service.py` covering every operation, duplicate-day rejection, and the validation cases.

## 5. Implement the summary service
Goal: Compute the task and habit counts needed by the `summary` command.
Description: Add `services/summary_service.py` with `get_summary(db)` returning total, pending, and completed task counts plus total habits and habits logged today, using the local date with an optional date parameter for tests. Keep it read-only and tolerant of an empty database. Add `tests/test_summary_service.py` covering an empty database and a mixed dataset.

## 6. Wire the `task` CLI commands
Goal: Expose task operations through `python main.py task ...` subcommands.
Description: Implement `commands/task.py` with `register(subparsers)` and handlers for `add`, `list`, `complete`, `uncomplete`, and `delete` per the shared conventions, including the friendly empty-list message. Handlers must load and save through `storage` and convert service `ValueError`s into a printed error with exit code 1. Add `tests/test_task_commands.py` using `argparse` and a temporary `DB_PATH` to verify output and persisted changes.

## 7. Wire the `habit` CLI commands
Goal: Expose habit operations through `python main.py habit ...` subcommands.
Description: Implement `commands/habit.py` with `register(subparsers)` and handlers for `add`, `list`, `log`, and `delete` per the shared conventions, including a helpful message when today's log already exists. Handlers must load and save through `storage` and convert service `ValueError`s into a printed error with exit code 1. Add `tests/test_habit_commands.py` using a temporary `DB_PATH` to verify output, duplicate-day rejection, and persisted changes.

## 8. Wire the `summary` CLI command
Goal: Expose the summary counts through `python main.py summary`.
Description: Implement `commands/summary.py` with `register(subparsers)` and a handler that reads the database through `storage`, calls `get_summary`, and prints all five counts in a readable format. Follow the shared conventions for error handling and exit codes. Add `tests/test_summary_commands.py` using a temporary `DB_PATH` to check the output for empty and populated databases.

## 9. Connect the CLI entry point and add end-to-end tests
Goal: Make `python main.py ...` dispatch every command and verify the full workflow through the public interface.
Description: Update `main.py` to build the root argparse parser, call `register()` on all three command modules, and exit with the handler's return code. Add `tests/test_cli.py` that runs `main.py` in a subprocess with `HABIT_LOGGER_DB` pointed at a temporary file to verify persistence across runs, IDs continuing to increase after deletion, and invalid input returning a non-zero exit with a clear message. Confirm the help text lists `task`, `habit`, and `summary`.

## 10. Document usage in the README
Goal: Give a new user everything needed to run and test the CLI.
Description: Write `README.md` with the Python version requirement, how to run the tests, the full command reference from `_docs/plan.md`, and a note that data lives in `data/db.json` and can be reset by deleting it. Mention the once-per-day habit rule and the standard-library-only dependency. Keep it short and example-driven.
