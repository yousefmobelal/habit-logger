"""Pure in-memory business logic for one-time tasks."""

NAME_ERROR = "Task name must be a non-empty string."


def _validate_name(name):
    """Raise a ValueError unless *name* is a non-blank string."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError(NAME_ERROR)


def _validate_task_id(task_id):
    """Raise a ValueError unless *task_id* is a plain positive int."""
    if type(task_id) is not int or task_id <= 0:
        raise ValueError(f"Task id must be a positive integer, got {task_id!r}.")


def _task_index(db, task_id):
    """Return the index of the task with *task_id* or raise a ValueError."""
    for index, task in enumerate(db["tasks"]):
        if task["id"] == task_id:
            return index
    raise ValueError(f"No task found with id {task_id}.")


def add(db, name):
    """Add a new pending task named *name* and return the stored task dict."""
    _validate_name(name)
    task = {
        "id": db["next_task_id"],
        "name": name,
        "completed": False,
    }
    db["tasks"].append(task)
    db["next_task_id"] += 1
    return task


def list_tasks(db):
    """Return a shallow copy of the task list in insertion order."""
    return list(db["tasks"])


def complete(db, task_id):
    """Mark the task with *task_id* complete and return the stored task dict."""
    _validate_task_id(task_id)
    task = db["tasks"][_task_index(db, task_id)]
    task["completed"] = True
    return task


def uncomplete(db, task_id):
    """Mark the task with *task_id* pending and return the stored task dict."""
    _validate_task_id(task_id)
    task = db["tasks"][_task_index(db, task_id)]
    task["completed"] = False
    return task


def delete(db, task_id):
    """Remove and return the stored task dict with *task_id*."""
    _validate_task_id(task_id)
    return db["tasks"].pop(_task_index(db, task_id))
