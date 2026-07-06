from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import List, Optional


@dataclass
class Task:
    """Simple Task dataclass representing a pet care activity."""
    id: int
    title: str
    description: Optional[str] = ""
    due_date: Optional[datetime] = None
    recurring: bool = False
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

    def add_task(self, task: Task) -> None:
        """Attach a Task to this pet."""
        task.pet_id = self.id
        self.tasks.append(task)

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
        self.id = id
        self.name = name
        self.contact_info = contact_info
        self.pets: List[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        pet.owner_id = self.id
        self.pets.append(pet)

    def remove_pet(self, pet_id: int) -> None:
        self.pets = [p for p in self.pets if p.id != pet_id]

    def get_pets(self) -> List[Pet]:
        return list(self.pets)


class Scheduler:
    """Scheduler manages tasks across pets. This is intentionally small and synchronous."""

    def __init__(self):
        self.tasks: List[Task] = []

    def schedule_task(self, task: Task) -> None:
        self.tasks.append(task)

    def cancel_task(self, task_id: int) -> None:
        self.tasks = [t for t in self.tasks if t.id != task_id]

    def get_tasks_for_day(self, target_date: date) -> List[Task]:
        """Return tasks whose due_date falls on the provided date."""
        result: List[Task] = []
        for t in self.tasks:
            if t.due_date and t.due_date.date() == target_date:
                result.append(t)
        return sorted(result, key=lambda t: t.due_date)

    def run_due_tasks(self, now: Optional[datetime] = None) -> List[Task]:
        """Return the list of tasks that are due at or before `now` and are not completed.

        This method does not execute actions; it only selects and returns due tasks so
        the caller can act on them (notify, run, etc.).
        """
        now = now or datetime.now()
        due = [t for t in self.tasks if t.due_date and not t.completed and t.due_date <= now]
        return sorted(due, key=lambda t: t.due_date)
