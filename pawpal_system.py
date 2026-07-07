from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta, time
from typing import List, Optional


@dataclass
class ScheduleWarning:
    """Structured warning returned by scheduling/attachment helpers.

    message: human-friendly text describing the issue. This class implements
    __str__ so it can be used in places expecting a string warning.
    """
    message: str
    code: Optional[str] = None
    details: Optional[dict] = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


@dataclass
class Task:
    """Simple Task dataclass representing a pet care activity."""
    id: int
    title: str
    description: Optional[str] = ""
    due_date: Optional[datetime] = None
    # `recurring` kept for backward compatibility; `recurrence` can be 'daily' or 'weekly'
    recurring: bool = False
    recurrence: Optional[str] = None
    completed: bool = False
    pet_id: Optional[int] = None

    def mark_complete(self) -> None:
        """Mark the task as completed."""
        self.completed = True

    def snooze(self, minutes: int) -> None:
        """Push the due date forward by the given minutes (if a due_date exists)."""
        if self.due_date:
            self.due_date = self.due_date + timedelta(minutes=minutes)

    def is_overdue(self, now: Optional[datetime] = None) -> bool:
        """Return True if the task is past due and not completed."""
        if not self.due_date or self.completed:
            return False
        now = now or datetime.now()
        return now > self.due_date


@dataclass
class Pet:
    """Pet dataclass that holds basic pet info and a list of tasks."""
    id: int
    name: str
    species: Optional[str] = None
    breed: Optional[str] = None
    age: Optional[int] = None
    owner_id: Optional[int] = None
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> Optional[ScheduleWarning]:
        """Attach a Task to this pet."""
        # Avoid adding the same task twice to a pet (by id).
        # Return a structured ScheduleWarning when a duplicate is detected to
        # mirror Scheduler.schedule_task's behavior and make handling consistent.
        if any(existing.id == task.id for existing in self.tasks):
            return ScheduleWarning(
                message=f"task with id={task.id} is already attached to pet id={self.id}",
                code="duplicate_task",
                details={"task_id": task.id, "pet_id": self.id},
            )
        task.pet_id = self.id
        self.tasks.append(task)
        return None

    def remove_task(self, task_id: int) -> None:
        """Remove a task by id if present."""
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_upcoming_tasks(self) -> List[Task]:
        """Return tasks that are not completed, sorted by due date if available."""
        pending = [t for t in self.tasks if not t.completed]
        return sorted(pending, key=lambda t: t.due_date or datetime.max)


class Owner:
    """Owner holds references to their pets and simple management utilities."""

    def __init__(self, id: int, name: str, contact_info: Optional[str] = None):
        """Initialize an Owner with id, name, and optional contact info."""
        self.id = id
        self.name = name
        self.contact_info = contact_info
        self.pets: List[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a Pet to this owner and set the pet's owner_id."""
        pet.owner_id = self.id
        self.pets.append(pet)

    def remove_pet(self, pet_id: int) -> None:
        """Remove a pet from this owner by its id."""
        self.pets = [p for p in self.pets if p.id != pet_id]

    def get_pets(self) -> List[Pet]:
        """Return a list of this owner's pets."""
        return list(self.pets)


class Scheduler:
    """Scheduler manages tasks across pets. This is intentionally small and synchronous."""

    def __init__(self):
        """Create a Scheduler with an empty task collection."""
        self.tasks: List[Task] = []

    def schedule_task(self, task: Task) -> Optional[ScheduleWarning]:
        """Add a Task to the scheduler's task list, with lightweight conflict detection.

        This method attempts to append `task` to the scheduler's internal list. Instead of
        raising on duplicates or conflicts it returns a short warning message describing
        the potential issue; callers can choose to log, display, or ignore the message.

        Parameters:
        - task: Task to be scheduled.

        Returns:
        - None if the task was scheduled without any noteworthy conflicts.
        - A string starting with 'Warning:' describing duplicate/conflict details when
          a potential issue is detected. If the task is a duplicate (same id) it will
          not be added and a warning string is returned.

        Notes:
        - This is intentionally lightweight: it performs exact datetime and same-time
          checks but does not attempt to resolve conflicts. The caller remains in
          control of how to handle warnings.
        """
        # Lightweight conflict detection: when scheduling, do not raise exceptions.
        # Instead, return a short warning message if a potential conflict or duplicate is detected.
        # Keep behavior backward compatible (still appends the task when appropriate).

        # Avoid scheduling the same task more than once (by id).
        if any(existing.id == task.id for existing in self.tasks):
            # Duplicate: do not add again, but warn the caller.
            return ScheduleWarning(
                message=f"task with id={task.id} is already scheduled",
                code="duplicate_task",
                details={"task_id": task.id},
            )

        # If the task has a due_date, detect exact-datetime conflicts and same time-of-day conflicts
        # on the same date. Build a lightweight warning message but still schedule the task.
        warning_parts: List[str] = []
        if task.due_date:
            exact_conflicts = [e for e in self.tasks if e.due_date and e.due_date == task.due_date]
            if exact_conflicts:
                conflict_descriptions = [f"{c.title}(id={c.id},pet_id={c.pet_id})" for c in exact_conflicts]
                warning_parts.append(f"exact datetime conflict with: {', '.join(conflict_descriptions)}")

            same_time_conflicts = [e for e in self.tasks if e.due_date and e.due_date.date() == task.due_date.date() and e.due_date.time() == task.due_date.time()]
            # same_time_conflicts may include exact_conflicts; avoid duplicating the message
            if same_time_conflicts and len(same_time_conflicts) > len(exact_conflicts):
                conflict_descriptions = [f"{c.title}(id={c.id},pet_id={c.pet_id})" for c in same_time_conflicts if c not in exact_conflicts]
                if conflict_descriptions:
                    warning_parts.append(f"same time-of-day on {task.due_date.date()} with: {', '.join(conflict_descriptions)}")

        # Append the task (normal behavior)
        self.tasks.append(task)

        if warning_parts:
            # Return a structured ScheduleWarning so callers can inspect details.
            return ScheduleWarning(
                message="; ".join(warning_parts),
                code="conflict",
                details={"task_id": task.id, "warnings": warning_parts},
            )

        return None

    def complete_task(self, task_id: int, pets: Optional[List[Pet]] = None) -> Optional[Task]:
        """Mark a task as completed and, if it recurs daily/weekly, schedule the next occurrence.

        If `pets` is provided, the new occurrence will also be added to the corresponding Pet.tasks list.
        Returns the newly created Task for the next occurrence, or None if no recurrence was scheduled.
        """
        task = next((t for t in self.tasks if t.id == task_id), None)
        if task is None:
            return None

        task.mark_complete()

        # Determine recurrence rule: explicit .recurrence takes precedence; if not set but
        # .recurring is True, assume daily recurrence for backward compatibility.
        recurrence = task.recurrence or ("daily" if task.recurring else None)
        if recurrence not in ("daily", "weekly"):
            return None

        if not task.due_date:
            return None

        delta = timedelta(days=1) if recurrence == "daily" else timedelta(days=7)
        new_due = task.due_date + delta

        # Choose a new id (one greater than the current max id across scheduled tasks)
        existing_ids = [t.id for t in self.tasks]
        new_id = (max(existing_ids) + 1) if existing_ids else 1

        new_task = Task(
            id=new_id,
            title=task.title,
            description=task.description,
            due_date=new_due,
            recurring=task.recurring,
            recurrence=recurrence,
        )
        new_task.pet_id = task.pet_id

        # Schedule and attach to pet (if pets provided)
        self.schedule_task(new_task)
        if pets is not None:
            pet = next((p for p in pets if p.id == new_task.pet_id), None)
            if pet:
                pet.add_task(new_task)

        return new_task

    def cancel_task(self, task_id: int) -> None:
        """Remove a Task from the scheduler by its id."""
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_tasks_for_day(self, target_date: date) -> List[Task]:
        """Return tasks whose due_date falls on the provided date."""
        result: List[Task] = []
        for t in self.tasks:
            if t.due_date and t.due_date.date() == target_date:
                result.append(t)
        return sorted(result, key=lambda t: t.due_date)

    def sort_by_time(self, tasks: Optional[List[Task]] = None, reverse: bool = False) -> List[Task]:
        """Return tasks sorted by time-of-day (due_date's time component).

        A stable, in-memory helper that orders tasks by their clock time regardless of
        date. Tasks without a `due_date` are treated as having time.min so they appear
        before timed tasks when sorting ascending.

        Parameters:
        - tasks: optional list of Task objects to sort; if None the scheduler's tasks
          list is used.
        - reverse: whether to reverse the sort order.

        Returns:
        - A new list containing the tasks sorted by their time-of-day.

        Complexity: O(n log n) due to sorting.
        """
        task_list = tasks if tasks is not None else self.tasks
        # Use time.min for tasks without a due_date so they sort predictably
        return sorted(task_list, key=lambda t: (t.due_date.time() if t.due_date else time.min), reverse=reverse)

    def filter_tasks(self, *, completed: Optional[bool] = None, pet_name: Optional[str] = None, pets: Optional[List[Pet]] = None) -> List[Task]:
        """Return tasks filtered by completion status and/or pet name.

        This convenience method supports two common filters used by the calling code:
        whether a task is completed and an optionally case-insensitive substring match
        against a pet's name.

        Parameters:
        - completed: if True returns only completed tasks, if False only incomplete
          tasks, if None no filtering is applied by completion.
        - pet_name: case-insensitive substring match against pet.name. If provided,
          the `pets` parameter must also be supplied so pet_id values can be resolved
          to names.
        - pets: list of Pet objects used to resolve pet_id -> pet name when pet_name
          filtering is requested.

        Returns:
        - A list of Task objects matching the requested filters (possibly empty).

        Complexity: O(n + m) where n is number of scheduled tasks and m is number of
        pets when pet_name filtering is used.
        """
        results: List[Task] = list(self.tasks)

        if completed is not None:
            results = [t for t in results if t.completed is completed]

        if pet_name is not None:
            if pets is None:
                raise ValueError("pet_name filter requires a 'pets' list to resolve pet ids")
            # build id -> name mapping for fast lookup
            id_to_name = {p.id: p.name for p in pets}
            needle = pet_name.lower()
            # allow substring match (case-insensitive) so partial names work
            results = [t for t in results if (id_to_name.get(t.pet_id, "").lower().find(needle) != -1)]

        return results

    def run_due_tasks(self, now: Optional[datetime] = None) -> List[Task]:
        """Return the list of tasks that are due at or before `now` and are not completed.

        This method does not execute actions; it only selects and returns due tasks so
        the caller can act on them (notify, run, etc.).
        """
        now = now or datetime.now()
        due = [t for t in self.tasks if t.due_date and not t.completed and t.due_date <= now]
        return sorted(due, key=lambda t: t.due_date)

    def detect_conflicts(self) -> List[List[Task]]:
        """Detect tasks that are scheduled at the exact same datetime.

        This returns groups of tasks whose `due_date` datetimes are identical. Each
        returned group contains at least two tasks and represents a true collision
        at the precise datetime level (date + time). The method is intended for
        reporting and does not mutate scheduler state.

        Returns:
        - A list of lists; each inner list contains Task objects that collide.
        """
        by_dt: dict[datetime, List[Task]] = {}
        for t in self.tasks:
            if not t.due_date:
                continue
            by_dt.setdefault(t.due_date, []).append(t)

        return [group for group in by_dt.values() if len(group) > 1]

    def find_conflicts_for_pet(self, pet_id: int) -> List[List[Task]]:
        """Detect conflicting tasks for a single pet (exact same due_date).

        Parameters:
        - pet_id: integer id of the pet to check.

        Returns:
        - A list of conflict groups (each group is a list of Task objects) for the
          specified pet. Each group has more than one task.
        """
        by_dt: dict[datetime, List[Task]] = {}
        for t in self.tasks:
            if t.pet_id != pet_id or not t.due_date:
                continue
            by_dt.setdefault(t.due_date, []).append(t)
        return [group for group in by_dt.values() if len(group) > 1]

    def get_time_conflicts_for_day(self, target_date: date) -> List[List[Task]]:
        """Detect tasks on a given date that share the same time-of-day.

        Use this when you want to flag collisions by clock time (e.g., two tasks both
        scheduled at 10:30 on the target date) even if the underlying datetimes are
        not stored with identical timezone information.

        Parameters:
        - target_date: date to inspect.

        Returns:
        - A list of groups (lists of Task) where each group contains tasks sharing the
          same time-of-day on the requested date. Groups contain at least two tasks.
        """
        by_time: dict[time, List[Task]] = {}
        for t in self.tasks:
            if not t.due_date:
                continue
            if t.due_date.date() != target_date:
                continue
            by_time.setdefault(t.due_date.time(), []).append(t)
        return [group for group in by_time.values() if len(group) > 1]
