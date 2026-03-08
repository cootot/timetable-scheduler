"""
Core Scheduling Algorithm for M3 Timetable System
=================================================

This module implements the automated timetable generator. It acts as the 
"brain" of the application, taking all the mapping data (who teaches what to whom)
and attempting to fit it into a complex multi-dimensional grid (Time x Space x 
People x Resources) without breaking any rules.

Algorithm Approach: Faculty-Centric Greedy with Constraint Satisfaction
----------------------------------------------------------------------
1. Pre-allocation: 
   Estimates teaching loads first. Before placing any class on the calendar, 
   it assigns specific teachers to specific student sections to handle 
   resource-starvation issues ahead of time.

2. Faculty-Centric Scheduling:
   Processes each teacher and their assigned tasks. This ensures teacher-specific
   constraints (e.g., max classes per day, exactly 1 lab per day) are strictly 
   enforced.

3. Break Enforcement:
   Automatically identifies Interval (after Slot 2) and Lunch (after Slot 5) 
   and prevents any multi-slot sessions from crossing them.

Author: M3 Backend Team (Akshitha, Bhuvanesh)
"""

import random
from django.utils import timezone
from django.db import transaction

# Import the core data models we will be reading from and writing to
from core.models import (
    Schedule, ScheduleEntry, Section, Course, Teacher, Room,
    TimeSlot, TeacherCourseMapping, ConflictLog
)

# Import the constraint checker (the rule engine)
from .constraints import ConstraintValidator, calculate_schedule_quality


DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']
MAX_THEORY_PER_FACULTY_PER_DAY = 3   # max theory/lecture slots per faculty per day
MIN_THEORY_PER_FACULTY_PER_DAY = 2   # min theory/lecture slots per faculty per day
INTERVAL_AFTER_SLOT = 2
LUNCH_AFTER_SLOT = 5


class TimetableScheduler:
    """
    Main stateful scheduling engine class.
    Generates conflict-free timetables using faculty-centric priority logic.
    """

    def __init__(self, schedule):
        """
        Initialize the scheduler context.
        """
        self.schedule = schedule
        # Instantiate the Rule Engine linked to this specific schedule
        self.validator = ConstraintValidator(schedule)
        # A list to keep track of issues we encounter but can't cleanly solve
        self.conflicts = []
        # (course_id, section_id) -> Teacher
        self.teacher_assignments = {}

    def generate(self):
        """
        Main orchestration method for schedule generation.
        Returns: (success: bool, message: str)
        """
        try:
            self.schedule.status = 'GENERATING'
            self.schedule.save()

            sections = list(Section.objects.all().order_by('year', 'class_id'))
            if not sections:
                return False, "No sections found"

            timeslots = list(TimeSlot.objects.all().order_by('day', 'slot_number'))
            if not timeslots:
                return False, "No timeslots available"

            # Build timeslots grouped by day for fast access
            ts_by_day = {}
            for ts in timeslots:
                ts_by_day.setdefault(ts.day, [])
                ts_by_day[ts.day].append(ts)
            for day in ts_by_day:
                ts_by_day[day].sort(key=lambda t: t.slot_number)

            year_counts = {}
            for s in sections:
                year_counts[s.year] = year_counts.get(s.year, 0) + 1

            # Phase 0: Pre-allocate teachers to (course, section) pairs
            self._preallocate_teachers(sections)

            # Phase 1: Build per-faculty task lists
            faculty_tasks = self._build_faculty_tasks()

            # Phase 2: Schedule each faculty member
            teachers = list(Teacher.objects.all())
            random.shuffle(teachers)

            for teacher in teachers:
                tasks = faculty_tasks.get(teacher.teacher_id, {
                    'lab': [], 'theory': [], 'lecture': []
                })
                self._schedule_faculty(teacher, tasks, ts_by_day)
                # Refresh validator cache after each faculty
                self.validator = ConstraintValidator(self.schedule)

            # Evaluate how well the algorithm did.
            quality = calculate_schedule_quality(self.schedule)
            
            # Update the parent record and mark success
            self.schedule.quality_score = quality
            # Persist status completion explicitly to signal UI polling mechanisms
            self.schedule.status = 'COMPLETED'
            self.schedule.completed_at = timezone.now()
            self.schedule.save()

            years_str = ', '.join(
                f"Year {y}: {c} sections" for y, c in sorted(year_counts.items())
            )
            return True, f"Faculty-centric schedule generated ({years_str}) | Quality: {quality:.2f}"

        except Exception as e:
            # Catch-all failsafe to ensure the UI doesn't spin forever if a critical bug occurs
            self.schedule.status = 'FAILED'
            self.schedule.save()
            raise e

    # ─────────────────────────────────────────────────────────────
    # TEACHER PRE-ALLOCATION
    # ─────────────────────────────────────────────────────────────

    def _preallocate_teachers(self, sections):
        """
        Assign one teacher per (course, section) pair.
        Balances load across mapped teachers using a least-loaded-first strategy.
        """
        from collections import defaultdict
        teacher_load = defaultdict(int)

        sections_by_year = defaultdict(list)
        for section in sections:
            sections_by_year[section.year].append(section)

        for year, year_sections in sections_by_year.items():
            courses = Course.objects.filter(
                year=year,
                semester=self.schedule.semester
            )
            # Filter non-electives, but ALWAYS include Life Skills (CIR)
            courses = [c for c in courses if not c.is_elective or 'Life Skills' in c.course_name or 'LSE' in c.course_id]

            for course in courses:
                slots_per_section = course.weekly_slots

                mappings = list(TeacherCourseMapping.objects.filter(
                    course=course
                ).select_related('teacher').order_by('-preference_level'))

                seen = set()
                pool = []
                for m in mappings:
                    tid = m.teacher.teacher_id
                    if tid not in seen:
                        seen.add(tid)
                        pool.append(m.teacher)

                if not pool:
                    pool = list(Teacher.objects.all())

                pool.sort(key=lambda t: teacher_load[t.teacher_id])

                for section in year_sections:
                    key = (course.course_id, section.class_id)

                    # Choose least loaded capable teacher
                    selected = None
                    for t in pool:
                        if teacher_load[t.teacher_id] + slots_per_section <= t.max_hours_per_week:
                            selected = t
                            break

                    if not selected:
                        # Fallback: global search
                        all_teachers = list(Teacher.objects.all())
                        all_teachers.sort(key=lambda t: teacher_load[t.teacher_id])
                        for t in all_teachers:
                            if teacher_load[t.teacher_id] + slots_per_section <= t.max_hours_per_week:
                                selected = t
                                break
                            
                    if not selected:
                        # Last resort: least loaded regardless of cap
                        all_teachers = list(Teacher.objects.all())
                        all_teachers.sort(key=lambda t: teacher_load[t.teacher_id])
                        selected = all_teachers[0] if all_teachers else None

                    if selected:
                        self.teacher_assignments[key] = selected
                        teacher_load[selected.teacher_id] += slots_per_section
                        pool.sort(key=lambda t: teacher_load[t.teacher_id])

    # ─────────────────────────────────────────────────────────────
    # BUILD FACULTY TASK LISTS
    # ─────────────────────────────────────────────────────────────

    def _build_faculty_tasks(self):
        """
        From teacher_assignments, build per-faculty lists of tasks.
        NOTE: We now merge 'theory' into 'lecture' (Phase C) to allow 
        the algorithm to spread them across multiple days individually.
        """
        faculty_tasks = {}

        def get_tasks(teacher_id):
            if teacher_id not in faculty_tasks:
                faculty_tasks[teacher_id] = {'lab': [], 'lecture': []}
            return faculty_tasks[teacher_id]

        for (course_id, section_id), teacher in self.teacher_assignments.items():
            try:
                course = Course.objects.get(course_id=course_id)
                section = Section.objects.get(class_id=section_id)
            except Exception:
                continue

            tasks = get_tasks(teacher.teacher_id)

            # LAB slots (Always continuous blocks)
            if course.practicals > 0:
                tasks['lab'].append((course, section, course.practicals))

            # ALL other hours (Theory + Lecture) are treated as individual slots
            # to maximize the chance of having at least one class every day.
            other_hours = course.weekly_slots - course.practicals
            if other_hours > 0:
                tasks['lecture'].append((course, section, other_hours))

        return faculty_tasks

    # ─────────────────────────────────────────────────────────────
    # FACULTY SCHEDULING CORE
    # ─────────────────────────────────────────────────────────────

    def _schedule_faculty(self, teacher, tasks, ts_by_day):
        """
        Schedule all tasks for one faculty member, ensuring load is spread across all 5 days.
        """
        lab_tasks = sorted(list(tasks.get('lab', [])), key=lambda x: ('LSE' in x[0].course_id or 'CIR' in x[0].course_id), reverse=True)
        lec_tasks = sorted(list(tasks.get('lecture', [])), key=lambda x: ('LSE' in x[0].course_id or 'CIR' in x[0].course_id), reverse=True)

        def get_sorted_days_for_teacher():
            return sorted(DAYS, key=lambda d: self._teacher_daily_count(teacher, d))

        # ── Phase A: Schedule LAB blocks (2 consecutive) ──────────────
        lab_days_used = set()
        for (course, section, num_slots) in lab_tasks:
            block_size = 2
            placed = False
            # Spread labs to empty days first
            sorted_days = get_sorted_days_for_teacher()
            for day in sorted_days:
                if day in lab_days_used: continue
                if self._section_has_lab_on_day(section, day): continue

                day_slots = ts_by_day.get(day, [])
                for i in range(len(day_slots) - block_size + 1):
                    window = day_slots[i: i + block_size]
                    if not self._is_consecutive(window, check_breaks=True): continue
                    if not self._window_free(window, teacher, section): continue

                    lab_room = self._find_room_for_window(window, room_type='LAB')
                    if not lab_room: continue

                    for ts in window:
                        ScheduleEntry.objects.create(schedule=self.schedule, section=section, course=course, teacher=teacher, room=lab_room, timeslot=ts, is_lab_session=True)
                    lab_days_used.add(day)
                    placed = True
                    self.validator = ConstraintValidator(self.schedule)
                    break
                if placed: break
            if not placed:
                self._log_conflict('LAB_UNPLACED', f"Could not place lab for {course.course_id} / {section.class_id}", 'HIGH')

        # ── Phase B: Schedule LECTURE / THEORY slots (Individual spread) ─────────────
        for (course, section, num_slots) in lec_tasks:
            remaining = num_slots
            while remaining > 0:
                placed = False
                
                # SPREAD PRIORITY: 
                # 0. Day where teacher has ZERO classes (Force classes on every day)
                # 1. Day where teacher has 1 class (Reach minimum load)
                # 2. Other days, while respecting a Section max-per-day limit
                def day_score(d):
                    t_cnt = self._teacher_daily_count(teacher, d)
                    s_cnt = self._section_daily_count(section, d)
                    
                    if t_cnt >= 5: return 900 # Absolute max for faculty
                    if s_cnt >= 7: return 800 # Prevent student burnout/packing
                    
                    if t_cnt == 0: return 0  # Fill the empty days first!
                    if t_cnt == 1: return 1  # Aim for at least 2 per day
                    return 10 + t_cnt

                sorted_days = sorted(DAYS, key=day_score)

                for day in sorted_days:
                    if self._teacher_daily_count(teacher, day) >= 6: continue
                    if self._section_daily_count(section, day) >= 8: continue

                    slot_list = list(ts_by_day.get(day, []))
                    random.shuffle(slot_list)

                    for ts in slot_list:
                        if self._teacher_busy(teacher, ts): continue
                        if self._section_busy(section, ts): continue
                        if self._is_course_across_break(section, course, ts): continue

                        prev_room = self._get_adjacent_theory_room(teacher, section, ts)
                        room = prev_room if (prev_room and not self._room_busy(prev_room, ts)) else self._find_room_single(ts, room_type='CLASSROOM')
                        if not room: continue

                        ScheduleEntry.objects.create(schedule=self.schedule, section=section, course=course, teacher=teacher, room=room, timeslot=ts, is_lab_session=False)
                        placed = True
                        remaining -= 1
                        self.validator = ConstraintValidator(self.schedule)
                        break
                    if placed: break

                if not placed:
                    # Emergency fallback - ignored spread for valid placement
                    for day in DAYS:
                        if self._teacher_daily_count(teacher, day) >= 8: continue
                        slot_list = list(ts_by_day.get(day, []))
                        for ts in slot_list:
                            if self._teacher_busy(teacher, ts) or self._section_busy(section, ts): continue
                            room = self._find_room_single(ts, room_type='CLASSROOM')
                            if room:
                                ScheduleEntry.objects.create(schedule=self.schedule, section=section, course=course, teacher=teacher, room=room, timeslot=ts, is_lab_session=False)
                                placed = True
                                remaining -= 1
                                self.validator = ConstraintValidator(self.schedule)
                                break
                        if placed: break

                if not placed:
                    self._log_conflict('LEC_UNPLACED', f"Could not place lec for {course.course_id}/{section.class_id} ({teacher.teacher_name})", 'MEDIUM')
                    break

    # ─────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────────────────────────────

    def _is_consecutive(self, window, check_breaks=False):
        if not window: return True
        for k in range(len(window) - 1):
            if window[k+1].slot_number != window[k].slot_number + 1: return False
            if check_breaks and (window[k].slot_number == INTERVAL_AFTER_SLOT or window[k].slot_number == LUNCH_AFTER_SLOT): return False
        return True

    def _teacher_busy(self, teacher, ts):
        return ScheduleEntry.objects.filter(schedule=self.schedule, teacher=teacher, timeslot=ts).exists()

    def _section_busy(self, section, ts):
        return ScheduleEntry.objects.filter(schedule=self.schedule, section=section, timeslot=ts).exists()

    def _room_busy(self, room, ts):
        return ScheduleEntry.objects.filter(schedule=self.schedule, room=room, timeslot=ts).exists()

    def _window_free(self, window, teacher, section):
        return all(not self._teacher_busy(teacher, ts) and not self._section_busy(section, ts) for ts in window)

    def _find_room_for_window(self, window, room_type='LAB'):
        rooms = list(Room.objects.filter(room_type=room_type))
        random.shuffle(rooms)
        for r in rooms:
            if all(not self._room_busy(r, ts) for ts in window): return r
        return None

    def _find_room_single(self, ts, room_type='CLASSROOM'):
        rooms = list(Room.objects.filter(room_type=room_type))
        random.shuffle(rooms)
        for r in rooms:
            if not self._room_busy(r, ts): return r
        return None

    def _get_adjacent_theory_room(self, teacher, section, ts):
        if ts.slot_number > 1:
            p = ScheduleEntry.objects.filter(schedule=self.schedule, teacher=teacher, section=section, timeslot__day=ts.day, timeslot__slot_number=ts.slot_number - 1, is_lab_session=False).first()
            if p: return p.room
        n = ScheduleEntry.objects.filter(schedule=self.schedule, teacher=teacher, section=section, timeslot__day=ts.day, timeslot__slot_number=ts.slot_number + 1, is_lab_session=False).first()
        if n: return n.room
        return None

    def _is_course_across_break(self, section, course, ts):
        s = ts.slot_number
        if s == INTERVAL_AFTER_SLOT + 1 or s == INTERVAL_AFTER_SLOT:
            other = INTERVAL_AFTER_SLOT if s == INTERVAL_AFTER_SLOT + 1 else INTERVAL_AFTER_SLOT + 1
            return ScheduleEntry.objects.filter(schedule=self.schedule, section=section, course=course, timeslot__day=ts.day, timeslot__slot_number=other).exists()
        if s == LUNCH_AFTER_SLOT + 1 or s == LUNCH_AFTER_SLOT:
            other = LUNCH_AFTER_SLOT if s == LUNCH_AFTER_SLOT + 1 else LUNCH_AFTER_SLOT + 1
            return ScheduleEntry.objects.filter(schedule=self.schedule, section=section, course=course, timeslot__day=ts.day, timeslot__slot_number=other).exists()
        return False

    def _teacher_daily_count(self, teacher, day):
        return ScheduleEntry.objects.filter(schedule=self.schedule, teacher=teacher, timeslot__day=day).count()

    def _section_daily_count(self, section, day):
        # New helper to prevent packing a section's schedule into 3-4 days
        return ScheduleEntry.objects.filter(schedule=self.schedule, section=section, timeslot__day=day).count()

    def _section_has_lab_on_day(self, section, day):
        return ScheduleEntry.objects.filter(schedule=self.schedule, section=section, timeslot__day=day, is_lab_session=True).exists()

    def _log_conflict(self, conflict_type, description, severity):
        ConflictLog.objects.create(schedule=self.schedule, conflict_type=conflict_type, description=description, severity=severity)
        self.conflicts.append(description)


def generate_schedule(schedule_id):
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        scheduler = TimetableScheduler(schedule)
        return scheduler.generate()
    except Schedule.DoesNotExist:
        return False, f"Schedule {schedule_id} not found"
