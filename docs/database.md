# Timetable Scheduler Database Architecture

The platform uses a robust relational architecture structured on PostgreSQL (or SQLite locally). The database is split natively into functional domains: **Core Academic Data**, **Algorithmic State**, and **Governance Operations**.

Django’s ORM serves as the primary gateway, enforcing strict foreign key constraints between teachers, rooms, and algorithmic allocations.

## Entity Relationship Summary

### 1. Academic Resources (The Constraints Base)

The entities in this module form the mathematical boundary within which the Scheduling Engine solves constraints.

- **`Teacher`**: Represents faculty constraints.
  - Primary Key: `teacher_id` (e.g., "T001").
  - Tracks: `department`, matching `email`, and hard-limit `max_hours_per_week`.
  
- **`Room`**: Physical constraints.
  - PK: `room_id`.
  - Tracks: `room_type` ('CLASSROOM' or 'LAB') which limits what `Course` can be scheduled there.

- **`Course`**: Represents subject curriculum logic.
  - PK: `course_id`.
  - Tracks core structures required for calculations: `lectures`, `theory`, `practicals`, `is_elective`, and `elective_group` (Vital for tracking parallel elective assignments).
  
- **`Section`**: Student groupings constrained by concurrent time blocks.
  - Tracks: `year`, `department`.

- **`TimeSlot`**: Fixed scheduling intervals grid.
  - Composite logic of `day` (MON-FRI) and `slot_number` (1-8).

### 2. Algorithmic State (`Schedule` & `ScheduleEntry`)

This domain holds the generated outputs of the backend scheduling process.

- **`Schedule`**
  - Represents an entire generation task instance.
  - Tracks: `semester` ("odd" or "even"), `year`, `status` (`PENDING`, `GENERATING`, `COMPLETED`, `FAILED`), and `is_historical`.
  
- **`ScheduleEntry`**
  - The granular building block of the resulting UI Grid.
  - Links exactly one `Course`, `Section`, `Teacher`, `Room`, and `TimeSlot` together against a specific `Schedule`.
  - Also tracks `session_type` (e.g., 'LAB', 'PE', 'LECTURE').

### 3. Governance Operations

These tables deal with lifecycle changes and platform supervision.

- **`TeacherCourseMapping`**
  - A pre-generation requirement table dictating who teaches what section. Read by the generation engine to build combinations.
- **`ChangeRequest`**
  - State machine storing requests by standard Faculty asking HODs to modify an active `ScheduleEntry`.
  - Tracks: `status` (`PENDING`, `APPROVED`, `REJECTED`).
- **`AuditLog`**
  - Immutable system logging table attached via Django Signals capturing significant mutations (Backups created, Rollovers initiated).

## Common Queries & Optimization

Indexes are heavily utilized to speed up the rendering of the `ScheduleEntry` grid table on the frontend.
The `ScheduleDetailSerializer` heavily pre-fetches nested relational keys:

```python
entries = ScheduleEntry.objects.filter(schedule=instance).select_related(
    'section', 'course', 'teacher', 'room', 'timeslot'
)
```

## Data Lifecycle

Due to massive data bloating over thousands of `ScheduleEntry` operations each semester:
1. **Semester Rollover Script (`manage.py rollover`):** Freezes the current state, drops all active mapping and unneeded scratch records, tags all existing `Schedule` instances as `is_historical=True`.
2. **Backups (`manage.py backup_db`):** Creates `.json` dumps of the database capable of completely reconstructing an exact prior state via Django's `loaddata` parser.
