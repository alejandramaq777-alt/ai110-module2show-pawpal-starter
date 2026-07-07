from pawpal_system import Task, Pet


def test_mark_complete_changes_status():
	t = Task(id=1, title="Feeding")
	assert not t.completed
	t.mark_complete()
	assert t.completed


def test_add_task_increases_count():
	p = Pet(id=1, name="Chanel")
	initial = len(p.tasks)
	t = Task(id=2, title="Walk")
	p.add_task(t)
	assert len(p.tasks) == initial + 1
	# ensure the task was linked to the pet
	assert p.tasks[-1].pet_id == p.id


def test_tasks_returned_in_chronological_order():
	from datetime import datetime, date, time
	from pawpal_system import Scheduler

	today = date.today()
	s = Scheduler()

	# Create tasks with distinct times and schedule them in a mixed order
	t1 = Task(id=10, title="T9", due_date=datetime.combine(today, time(hour=9, minute=0)))
	t2 = Task(id=11, title="T8", due_date=datetime.combine(today, time(hour=8, minute=0)))
	t3 = Task(id=12, title="T12", due_date=datetime.combine(today, time(hour=12, minute=0)))

	s.schedule_task(t1)
	s.schedule_task(t3)
	s.schedule_task(t2)

	sorted_tasks = s.sort_by_time(s.tasks)

	# Expect tasks ordered by time: 8:00, 9:00, 12:00
	expected_times = [time(8, 0), time(9, 0), time(12, 0)]
	actual_times = [t.due_date.time() for t in sorted_tasks]

	assert actual_times == expected_times


def test_completing_daily_task_creates_next_day():
	from datetime import datetime, date, time, timedelta
	from pawpal_system import Scheduler, Pet

	today = date.today()
	pet = Pet(id=5, name="Buddy")
	s = Scheduler()

	# create a daily recurring task for today at 9:00
	original_due = datetime.combine(today, time(hour=9, minute=0))
	task = Task(id=50, title="Feed", due_date=original_due, recurring=True)
	# attach to scheduler and pet
	s.schedule_task(task)
	pet.add_task(task)

	new_task = s.complete_task(task.id, pets=[pet])
	assert new_task is not None
	# new due date should be next day at same time
	expected = original_due + timedelta(days=1)
	assert new_task.due_date == expected
	# new task should be linked to the same pet id and present in pet.tasks
	assert new_task.pet_id == pet.id
	assert any(t.id == new_task.id for t in pet.tasks)
	# original task marked completed
	assert any(t.id == task.id and t.completed for t in s.tasks)


def test_completing_weekly_task_creates_next_week():
	from datetime import datetime, date, time, timedelta
	from pawpal_system import Scheduler, Pet

	today = date.today()
	pet = Pet(id=6, name="Rex")
	s = Scheduler()

	# create a weekly recurring task for today at 10:00
	original_due = datetime.combine(today, time(hour=10, minute=0))
	task = Task(id=60, title="Groom", due_date=original_due, recurrence="weekly")
	s.schedule_task(task)
	pet.add_task(task)

	new_task = s.complete_task(task.id, pets=[pet])
	assert new_task is not None
	# new due date should be 7 days later at same time
	expected = original_due + timedelta(days=7)
	assert new_task.due_date == expected
	assert new_task.pet_id == pet.id
	assert any(t.id == new_task.id for t in pet.tasks)
	assert any(t.id == task.id and t.completed for t in s.tasks)


def test_completing_recurring_task_without_due_date_returns_none_and_marks_completed():
	from pawpal_system import Scheduler, Pet
	s = Scheduler()
	pet = Pet(id=7, name="NoDate")

	# recurring flag true but no due_date
	task = Task(id=70, title="NoDue", recurring=True)
	s.schedule_task(task)
	pet.add_task(task)

	result = s.complete_task(task.id, pets=[pet])
	# should not create a new occurrence
	assert result is None
	# original task should be marked completed
	assert any(t.id == task.id and t.completed for t in s.tasks)
	# only the original task exists in scheduler (no new tasks created)
	assert len(s.tasks) == 1
