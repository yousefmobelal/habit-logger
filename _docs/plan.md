# CLI Task & Habit Logger — MVP Scope

**Version:** MVP v1  
**Status:** Scope defined

## 1. Project purpose

Build a command-based CLI application that combines two independent modules:

- **Task management:** manage one-time tasks.
- **Habit tracking:** record daily habit completions.

Both modules live in one CLI application but use separate command namespaces and workflows.

## 2. Technology and interface

- **Language:** Python
- **Interface:** Command-based CLI, inspired by tools such as Git.
- **Command parsing:** Python `argparse`.
- **Storage:** One local JSON file (`data/db.json`).
- **Dependencies:** Python standard library only.
- **Invocation:** Run the application with `python main.py ...`.

## 3. Task management

Supported operations:

- Add a task.
- List all tasks.
- Mark a task as completed.
- Mark a completed task as pending again.
- Permanently delete a task.

Tasks receive automatically generated incremental numeric IDs. Users identify tasks by ID.

Example commands:

```bash
python main.py task add "Study System Design"
python main.py task list
python main.py task complete 1
python main.py task uncomplete 1
python main.py task delete 1
```

Task functionality is intentionally basic. V1 does not include priorities, due dates, categories, tags, subtasks, recurring tasks, dependencies, or time tracking.

## 4. Habit tracking

Supported operations:

- Add a habit.
- List all habits.
- Log today's completion.
- Permanently delete a habit.

Habits receive automatically generated incremental numeric IDs. Users identify habits by ID.

**Daily logging rule:** A habit can only be logged once per calendar day. A repeated attempt on the same day must be rejected with a helpful message.

Example commands:

```bash
python main.py habit add "Read 30 minutes"
python main.py habit list
python main.py habit log 1
python main.py habit delete 1
```

V1 does not include configurable frequencies, streaks, completion-history views, custom schedules, or advanced reports.

## 5. Summary

Provide a `summary` command showing:

- Total number of tasks.
- Number of pending tasks.
- Number of completed tasks.
- Total number of habits.
- Number of habits completed today.

Example:

```bash
python main.py summary
```

## 6. Record identity and deletion

- Each task and habit has an automatically generated numeric ID.
- IDs are incremental and unique within their respective module.
- Names are not used as identifiers.
- Deletion is permanent: deleted records are removed from the JSON data.
- Editing existing tasks and habits is not supported in V1.

## 7. Listing behavior

- `task list` displays all existing tasks.
- `habit list` displays all existing habits.
- No filtering or sorting options are included in V1.
- If a list is empty, display a friendly message.

## 8. Validation and error handling

Implement basic validation and handle expected errors gracefully:

- Reject empty task or habit names.
- Reject malformed or invalid IDs.
- Handle IDs that do not correspond to an existing record.
- Handle a missing JSON file by initializing an empty database.
- Handle corrupted or invalid JSON with a clear error.
- Never silently overwrite corrupted data.

## 9. Data and date conventions

- Store all application data in one JSON file: `data/db.json`.
- Use the local system date when determining whether a habit has already been logged today.
- Persist data between application runs.

## 10. Proposed project structure

This is a practical starting point; adjust it only when implementation reveals a clear need.

```text
task-habit-logger/
│
├── main.py
├── commands/
│   ├── task.py
│   └── habit.py
│
├── services/
│   ├── task_service.py
│   └── habit_service.py
│
├── storage/
│   └── json_storage.py
│
├── data/
│   └── db.json
│
├── tests/
│   ├── test_task_service.py
│   ├── test_habit_service.py
│   └── test_json_storage.py
│
└── README.md
```

## 11. Full MVP command reference

```bash
# Tasks
python main.py task add "Study Python"
python main.py task list
python main.py task complete 1
python main.py task uncomplete 1
python main.py task delete 1

# Habits
python main.py habit add "Read 30 minutes"
python main.py habit list
python main.py habit log 1
python main.py habit delete 1

# Summary
python main.py summary
```

## 12. Testing

Use Python's built-in `unittest` framework.

At minimum, test:

- Adding, listing, completing, uncompleting, and deleting tasks.
- Adding, listing, logging, and deleting habits.
- Preventing a second completion log for the same habit on the same date.
- Summary counts.
- Invalid and nonexistent IDs.
- Empty names.
- Missing and corrupted JSON files.
- Persistence across application runs.

Tests should use temporary data files so they do not modify the user's real application data.

## 13. Explicitly out of scope for MVP

- Task priorities, due dates, categories, and tags.
- Subtasks, dependencies, recurring tasks, and time tracking.
- Habit frequencies and custom schedules.
- Streak calculations and habit-history views.
- Advanced statistics and reports.
- Editing tasks or habits.
- Filtering and sorting.
- Interactive menu-based interface.
- SQLite or other database systems.
- Third-party dependencies.
- Standalone executable packaging or system-wide installation.

These features can be reconsidered after the MVP is working and has been evaluated.

## 14. MVP acceptance criteria

The MVP is complete when:

1. A user can create, list, complete, uncomplete, and delete tasks using CLI commands.
2. A user can create, list, log today's completion for, and delete habits.
3. A habit cannot be logged more than once on the same local calendar date.
4. Every task and habit has an automatically generated numeric ID.
5. The summary reports the agreed task and habit counts correctly.
6. Data persists after the program exits and runs again.
7. Invalid input and storage errors produce understandable messages.
8. The automated tests pass.

## 15. Scope principle

Keep the MVP small and reliable. Prioritize clear command behavior, correct data handling, basic validation, persistence, and separation between command parsing, business logic, and storage. Avoid adding features beyond this scope until the core application works.

---

## Implementation defaults selected to close remaining decisions

The following choices were selected to complete the MVP definition without further questions:

| Decision | MVP choice |
|---|---|
| CLI invocation | `python main.py ...` |
| Command parser | `argparse` |
| Data file | One `data/db.json` file |
| Missing data file | Initialize an empty database |
| Corrupted JSON | Show an error; do not silently overwrite |
| Date handling | Local system date |
| IDs | Incremental numeric IDs, unique within each module |
| Empty lists | Friendly message |
| Dependencies | Standard library only |
| Testing | `unittest` with temporary data files |
| Packaging | Not included in MVP |
