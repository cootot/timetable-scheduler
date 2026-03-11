"""
Core Scheduling Algorithm for M3 Timetable System
=================================================

This module implements the automated timetable generator. It acts as the 
"brain" of the application, taking all the mapping data (who teaches what to whom)
and attempting to fit it into a complex multi-dimensional grid (Time x Space x 
People x Resources) without breaking any rules.

Algorithm Approach: Faculty-Centric Greedy with Constraint Satisfaction
----------------------------------------------------------------------
1. Pre-allocation (Strict Load Balanced): 
   Pre-calculates unavoidable loads (Electives, Projects) first. Then, honors 
   section-specific assignments and dynamically sorts fallback faculty by their 
   REAL-TIME percentage utilization. STRICTLY CAPS assignments at max_hours_per_week.

2. Load-Balanced Room Placement:
   Dynamically tracks room usage and sorts available rooms to pick the 
   least-utilized room first, flattening the room usage curve.

3. Break Enforcement:
   Automatically identifies Interval and Lunch slots and prevents multi-slot sessions.

Author: M3 Backend Team
"""

import random
from django.utils import timezone
from django.db import transaction

from core.models import (
    Schedule, ScheduleEntry, Section, Course, Teacher, Room,
    TimeSlot, TeacherCourseMapping, ConflictLog
)
from .constraints import ConstraintValidator, calculate_schedule_quality

DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']
INTERVAL_AFTER_SLOT = 2
LUNCH_AFTER_SLOT = 5

TYPE_PRACTICAL = 'PRACTICAL'
TYPE_LECTURE = 'LECTURE'
TYPE_TUTORIAL = 'TUTORIAL'
TYPE_ADM = 'ADM'
TYPE_PE = 'PE'
TYPE_FE = 'FE'

PRIORITY = {
    TYPE_PRACTICAL: 0,
    TYPE_PE: 1,
    TYPE_FE: 2,
    TYPE_ADM: 3,
    TYPE_LECTURE: 4,
    TYPE_TUTORIAL: 5,
}

class TimetableScheduler:
    def __init__(self, schedule):
        self.schedule = schedule
        self.validator = ConstraintValidator(schedule)
        self.conflicts = []
        self.teacher_assignments = {} 
        self.entries = [] 
        
        self.faculty_busy = {}   
        self.room_busy = {}      
        self.section_busy = {}   
        self.rooms_by_type = {'CLASSROOM': [], 'LAB': []}
        self.section_day_counts = {} 
        self.teacher_day_counts = {} 
        
        # Tracks how many times a room has been assigned to balance usage
        self.room_utilization = {} 
        self.iterations = 0
        self.MAX_ITERATIONS = 1000000

    def generate(self):
        try:
            self.schedule.status = 'GENERATING'
            self.schedule.save()
            ScheduleEntry.objects.filter(schedule=self.schedule).delete()

            sections = list(Section.objects.all().order_by('year', 'class_id'))
            if not sections: return False, "No sections found"

            timeslots = list(TimeSlot.objects.all().order_by('day', 'slot_number'))
            if not timeslots: return False, "No timeslots available"

            # Pre-load rooms into memory and initialize utilization trackers
            all_rooms = list(Room.objects.all())
            for r in all_rooms:
                self.rooms_by_type[r.room_type].append(r)
                self.room_utilization[r.room_id] = 0

            ts_by_day = {}
            for ts in timeslots:
                ts_by_day.setdefault(ts.day, [])
                ts_by_day[ts.day].append(ts)

            self._preallocate_teachers(sections)
            tasks = self._build_session_tasks(sections)
            
            # Prioritize tasks: Practicals > Electives > ADM > Lectures
            tasks.sort(key=lambda x: x['priority'])

            self.MAX_ITERATIONS = 5000
            success = self._backtrack_place(tasks, 0, ts_by_day)

            if not success:
                # Fallback to greedy approach
                self.entries = []
                self.faculty_busy.clear()
                self.room_busy.clear()
                self.section_busy.clear()
                for r in all_rooms: self.room_utilization[r.room_id] = 0
                
                for task in tasks:
                    placed = False
                    days = list(ts_by_day.keys())
                    
                    def get_day_load(d):
                        cnt = 0
                        task_secs = set(task.get('sections', []))
                        if task.get('sub_tasks'):
                            for st in task['sub_tasks']: task_secs.update(st.get('sections', []))
                        for s in task_secs:
                            cnt += sum(1 for (sid, day, slot), busy in self.section_busy.items() if busy and sid == s.class_id and day == d)
                        return cnt
                    
                    days.sort(key=get_day_load)

                    for day in days:
                        day_slots = ts_by_day.get(day, [])
                        for i in range(len(day_slots) - task['block_size'] + 1):
                            window = day_slots[i : i + task['block_size']]
                            if task.get('is_group'):
                                if self._can_place_group(task, window):
                                    self._place_group(task, window)
                                    placed = True
                                    break
                            else:
                                if self._can_place_single(task, window):
                                    self._place_single(task, window)
                                    placed = True
                                    break
                        if placed: break

            # Save whatever we managed to place
            with transaction.atomic():
                entries_to_create = [
                    ScheduleEntry(
                        schedule=self.schedule, section=e['section'], course=e['course'], 
                        teacher=e['teacher'], room=e['room'], timeslot=e['timeslot'],
                        is_lab_session=e['is_lab'], session_type=e['session_type'], constraint_reason=e.get('constraint_reason')
                    ) for e in self.entries
                ]
                ScheduleEntry.objects.bulk_create(entries_to_create)

            if not success:
                self.schedule.status = 'PARTIAL'
                self.schedule.save()
                return True, f"Generated partial timetable ({len(self.entries)}/{len(tasks)} tasks placed). Some constraints could not be met."

            quality = calculate_schedule_quality(self.schedule)
            self.schedule.quality_score = quality
            self.schedule.status = 'COMPLETED'
            self.schedule.completed_at = timezone.now()
            self.schedule.save()
            return True, f"Timetable generated successfully | Quality: {quality:.2f}"

        except Exception as e:
            self.schedule.status = 'FAILED'
            self.schedule.save()
            raise e

    def _preallocate_teachers(self, sections):
        """
        STRICT LOAD BALANCING PREALLOCATION
        Ensures teachers do not cross 100% utilization.
        """
        from collections import defaultdict
        teacher_load = defaultdict(int)
        
        # 1. PRE-CALCULATE ELECTIVE WORKLOAD
        electives = Course.objects.filter(is_elective=True, semester=self.schedule.semester, is_schedulable=True).exclude(elective_group__isnull=True)
        groups = defaultdict(list)
        for e in electives: groups[e.elective_group].append(e)
        
        for g_name, courses in groups.items():
            if not courses: continue
            base_course = courses[0]
            group_mappings = TeacherCourseMapping.objects.filter(course__in=courses).select_related('teacher')
            seen_teachers = set()
            for m in group_mappings:
                if m.teacher.teacher_id not in seen_teachers:
                    teacher_load[m.teacher.teacher_id] += base_course.weekly_slots
                    seen_teachers.add(m.teacher.teacher_id)

        # 2. PRE-CALCULATE & ASSIGN PROJECT PHASE WORKLOAD
        for section in sections:
            project_courses = Course.objects.filter(year=section.year, semester=self.schedule.semester, course_name__icontains="Project Phase")
            for pc in project_courses:
                mappings = TeacherCourseMapping.objects.filter(course=pc, section=section).select_related('teacher')
                if not mappings.exists():
                    mappings = TeacherCourseMapping.objects.filter(course=pc, section__isnull=True).select_related('teacher')
                
                if mappings.exists():
                    m = mappings.first()
                    self.teacher_assignments[(pc.course_id, section.class_id)] = m.teacher
                    
                    tracking_key = f"proj_{pc.course_id}_{m.teacher.teacher_id}"
                    if not hasattr(self, '_tracked_projects'): self._tracked_projects = set()
                    if tracking_key not in self._tracked_projects:
                        teacher_load[m.teacher.teacher_id] += pc.weekly_slots
                        self._tracked_projects.add(tracking_key)

        # 3. ALLOCATE CORE COURSES DYNAMICALLY (Strict Capping at Max Hours)
        for section in sections:
            courses = Course.objects.filter(year=section.year, semester=self.schedule.semester, is_elective=False).exclude(course_name__icontains="Project Phase")
            
            for course in courses:
                mappings = TeacherCourseMapping.objects.filter(course=course, section=section).select_related('teacher')
                if not mappings.exists():
                    mappings = TeacherCourseMapping.objects.filter(course=course, section__isnull=True).select_related('teacher')
                if not mappings.exists(): continue
                
                selected = None
                mappings_list = list(mappings)
                
                # Sort available teachers by their real-time utilization percentage
                mappings_list.sort(key=lambda m: teacher_load[m.teacher.teacher_id] / max(1.0, float(m.teacher.max_hours_per_week)))
                
                for m in mappings_list:
                    # STRICT CAP: Ensure load does not exceed max_hours_per_week (with absolute hard limit of 40)
                    cap = min(m.teacher.max_hours_per_week, 40)
                    if teacher_load[m.teacher.teacher_id] + course.weekly_slots <= cap:
                        selected = m.teacher
                        break
                        
                # Notice: The aggressive "safety net" has been removed here.
                # If a course pushes a teacher over 100%, they will NOT be assigned, strictly adhering to load constraints.
                
                if selected:
                    self.teacher_assignments[(course.course_id, section.class_id)] = selected
                    teacher_load[selected.teacher_id] += course.weekly_slots

    def _build_session_tasks(self, sections):
        tasks = []
        for (course_id, section_id), teacher in self.teacher_assignments.items():
            course = Course.objects.get(course_id=course_id)
            section = Section.objects.get(class_id=section_id)
            if "Project Phase" in course.course_name: continue

            if course.practicals > 0:
                tasks.append({ 'type': TYPE_PRACTICAL, 'course': course, 'sections': [section], 'teacher': teacher, 'block_size': course.practicals, 'priority': PRIORITY[TYPE_PRACTICAL], 'session_type': 'PRACTICAL' })
            for i in range(course.lectures):
                tasks.append({ 'type': TYPE_ADM if course.is_adm else TYPE_LECTURE, 'course': course, 'sections': [section], 'teacher': teacher, 'block_size': 1, 'priority': PRIORITY[TYPE_ADM if course.is_adm else TYPE_LECTURE], 'session_type': 'ADM' if course.is_adm else 'LECTURE' })
            for i in range(course.theory):
                tasks.append({ 'type': TYPE_TUTORIAL, 'course': course, 'sections': [section], 'teacher': teacher, 'block_size': 1, 'priority': PRIORITY[TYPE_TUTORIAL], 'session_type': 'TUTORIAL' })

        from collections import defaultdict
        electives = Course.objects.filter(is_elective=True, semester=self.schedule.semester, is_schedulable=True).exclude(elective_group__isnull=True)
        groups = defaultdict(list)
        for e in electives: groups[e.elective_group].append(e)

        for g_name, courses in groups.items():
            year = courses[0].year
            t_type = TYPE_FE if "FREE" in g_name.upper() else TYPE_PE
            s_type = 'FE' if t_type == TYPE_FE else 'PE'
            
            group_mappings = TeacherCourseMapping.objects.filter(course__in=courses).select_related('teacher', 'course', 'section')
            if not group_mappings: continue

            busy_teachers = set(m.teacher for m in group_mappings)
            target_sections = sorted([s for s in sections if s.year == year], key=lambda x: x.class_id)
            if not target_sections: continue

            base_course = courses[0]
            session_plan = []
            for _ in range(base_course.lectures): session_plan.append({'type': t_type, 'block_size': 1, 'session_type': s_type})
            for _ in range(base_course.theory): session_plan.append({'type': TYPE_TUTORIAL, 'block_size': 1, 'session_type': 'TUTORIAL'})
            if base_course.practicals > 0: session_plan.append({'type': TYPE_PRACTICAL, 'block_size': base_course.practicals, 'session_type': 'PRACTICAL'})

            for session in session_plan:
                sub_tasks = []
                task_busy_teachers = set()
                
                # Assign sections evenly across mapping to prevent duplicate entry bloat
                for idx, m in enumerate(group_mappings):
                    assigned_secs = [m.section] if m.section else [target_sections[idx % len(target_sections)]]
                    sub_tasks.append({ 'course': m.course, 'teacher': m.teacher, 'sections': assigned_secs, 'session_type': session['session_type'], 'display_name': m.course.course_name })
                    task_busy_teachers.add(m.teacher)
                
                if sub_tasks:
                    tasks.append({ 'type': session['type'], 'sub_tasks': sub_tasks, 'busy_teachers': list(task_busy_teachers), 'block_size': session['block_size'], 'priority': PRIORITY[session['type']], 'is_group': True, 'group_name': g_name })
        
        # Synchronous Project Phases 
        phases = defaultdict(list)
        for (course_id, section_id), teacher in self.teacher_assignments.items():
            course = Course.objects.get(course_id=course_id)
            if "Project Phase" in course.course_name:
                section = Section.objects.get(class_id=section_id)
                phases[course].append((section, teacher))
                
        for course, assignments in phases.items():
            for _ in range(course.practicals):
                sub_tasks = []
                task_busy_teachers = set()
                for section, teacher in assignments:
                    sub_tasks.append({ 'course': course, 'teacher': teacher, 'sections': [section], 'session_type': 'PRACTICAL' })
                    task_busy_teachers.add(teacher)
                if sub_tasks:
                    tasks.append({ 'type': TYPE_PRACTICAL, 'sub_tasks': sub_tasks, 'busy_teachers': list(task_busy_teachers), 'block_size': 1, 'priority': PRIORITY[TYPE_PRACTICAL], 'is_group': True, 'group_name': course.course_name, 'is_project': True })

        return tasks

    def _backtrack_place(self, tasks, index, ts_by_day):
        if getattr(self, 'abort_backtrack', False): return False
        self.iterations += 1
        if self.iterations > self.MAX_ITERATIONS:
            self.abort_backtrack = True
            return False
            
        if index >= len(tasks): return True
        task = tasks[index]
        
        def score_day(d):
            score = 0
            task_sections = set(task.get('sections', []))
            if task.get('sub_tasks'):
                for st in task['sub_tasks']: task_sections.update(st.get('sections', []))
            for sec in task_sections:
                if self.section_day_counts.get((sec.class_id, d), 0) == 0: score -= 100 
            teachers = set()
            if task.get('teacher'): teachers.add(task['teacher'])
            if task.get('sub_tasks'):
                for st in task['sub_tasks']:
                    if st.get('teacher'): teachers.add(st['teacher'])
            for t in teachers:
                if self.teacher_day_counts.get((t.teacher_id, d), 0) == 0: score -= 50 
            return score
            
        days = sorted(DAYS, key=score_day)
        
        for day in days:
            day_slots = ts_by_day.get(day, [])
            for i in range(len(day_slots) - task['block_size'] + 1):
                window = day_slots[i : i + task['block_size']]
                if task.get('is_group'):
                    if self._can_place_group(task, window):
                        added = self._place_group(task, window)
                        if self._backtrack_place(tasks, index + 1, ts_by_day): return True
                        if getattr(self, 'abort_backtrack', False): return False
                        self._remove_group(task, window, added)
                else:
                    if self._can_place_single(task, window):
                        added = self._place_single(task, window)
                        if self._backtrack_place(tasks, index + 1, ts_by_day): return True
                        if getattr(self, 'abort_backtrack', False): return False
                        self._remove_single(task, window, added)
        return False

    def _can_place_single(self, task, window):
        teacher = task['teacher']
        room_type = 'LAB' if task['type'] == TYPE_PRACTICAL else 'CLASSROOM'
        bypass = hasattr(self, 'iterations') and self.iterations > 300000

        for ts in window:
            if not bypass and self.faculty_busy.get((teacher.teacher_id, ts.day, ts.slot_number)): return False
            for section in task['sections']:
                if not bypass and self.section_busy.get((section.class_id, ts.day, ts.slot_number)): return False
        for k in range(len(window) - 1):
            if window[k].slot_number == INTERVAL_AFTER_SLOT or window[k].slot_number == LUNCH_AFTER_SLOT: return False

        if not bypass and not self._check_hc9(teacher, window): return False
        
        # ROOM LOAD BALANCING: Sort available rooms by lowest utilization
        rooms_sorted = sorted(self.rooms_by_type[room_type], key=lambda r: self.room_utilization.get(r.room_id, 0))
        for r in rooms_sorted:
            if bypass or not any(self.room_busy.get((r.room_id, ts.day, ts.slot_number)) for ts in window):
                task['selected_room'] = r
                return True
        return False

    def _place_single(self, task, window):
        teacher = task['teacher']
        room = task['selected_room']
        added = []
        for ts in window:
            ent = {'section': task['sections'][0], 'course': task['course'], 'teacher': teacher, 'room': room, 'timeslot': ts, 'is_lab': (task['type'] == TYPE_PRACTICAL), 'session_type': task['session_type']}
            self.entries.append(ent)
            added.append(ent)
            self.faculty_busy[(teacher.teacher_id, ts.day, ts.slot_number)] = True
            
            if room:
                self.room_busy[(room.room_id, ts.day, ts.slot_number)] = True
                self.room_utilization[room.room_id] = self.room_utilization.get(room.room_id, 0) + 1
            
            for sec in task['sections']: 
                self.section_busy[(sec.class_id, ts.day, ts.slot_number)] = True
                key = (sec.class_id, ts.day)
                self.section_day_counts[key] = self.section_day_counts.get(key, 0) + 1
            
            t_key = (teacher.teacher_id, ts.day)
            self.teacher_day_counts[t_key] = self.teacher_day_counts.get(t_key, 0) + 1
        return added

    def _remove_single(self, task, window, added):
        teacher = task['teacher']
        room = task['selected_room']
        for ent in added: 
            self.entries.remove(ent)
            ts = ent['timeslot']
            sec = ent['section']
            self.section_day_counts[(sec.class_id, ts.day)] -= 1
            self.teacher_day_counts[(teacher.teacher_id, ts.day)] -= 1
            
        for ts in window:
            self.faculty_busy[(teacher.teacher_id, ts.day, ts.slot_number)] = False
            if room:
                self.room_busy[(room.room_id, ts.day, ts.slot_number)] = False
                self.room_utilization[room.room_id] -= 1
            for sec in task['sections']: self.section_busy[(sec.class_id, ts.day, ts.slot_number)] = False

    def _can_place_group(self, task, window):
        ts = window[0]
        used_rooms = []
        bypass = hasattr(self, 'iterations') and self.iterations > 150000
        
        for t in task.get('busy_teachers', []):
            if not bypass and self.faculty_busy.get((t.teacher_id, ts.day, ts.slot_number)): return False
            
        for sub in task['sub_tasks']:
            for sec in sub['sections']:
                if not bypass and self.section_busy.get((sec.class_id, ts.day, ts.slot_number)): return False
            
            # Allow Project Phases to be placed without a room constraint
            if task.get('is_project'):
                sub['selected_room'] = None
                continue

            room_type = 'LAB' if sub['course'].practicals > 0 else 'CLASSROOM'
            
            # ROOM LOAD BALANCING: Sort available rooms by lowest utilization
            rooms_sorted = sorted(self.rooms_by_type[room_type], key=lambda r: self.room_utilization.get(r.room_id, 0))
            found_room = False
            for r in rooms_sorted:
                # Sub-tasks of the SAME group cannot be in the same room simultaneously
                if r not in used_rooms and (bypass or not self.room_busy.get((r.room_id, ts.day, ts.slot_number))):
                    sub['selected_room'] = r
                    used_rooms.append(r)
                    found_room = True
                    break
            if not found_room: return False
        return True

    def _place_group(self, task, window):
        ts = window[0]
        added = []
        processed_secs_for_day_count = set()
        
        for sub in task['sub_tasks']:
            teacher = sub['teacher']
            room = sub.get('selected_room')
            for sec in sub['sections']:
                is_lab = (sub['course'].practicals > 0)
                if sec.year == 4 and sub.get('session_type') in ['PE', 'FE', 'PRACTICAL']: is_lab = False
                    
                ent = {'section': sec, 'course': sub['course'], 'teacher': teacher, 'room': room, 'timeslot': ts, 'is_lab': is_lab, 'session_type': sub['session_type'], 'constraint_reason': sub.get('display_name')}
                self.entries.append(ent)
                added.append(ent)
                self.section_busy[(sec.class_id, ts.day, ts.slot_number)] = True
                
                key = (sec.class_id, ts.day)
                if key not in processed_secs_for_day_count:
                    self.section_day_counts[key] = self.section_day_counts.get(key, 0) + 1
                    processed_secs_for_day_count.add(key)
            
            if room:
                self.room_busy[(room.room_id, ts.day, ts.slot_number)] = True
                self.room_utilization[room.room_id] = self.room_utilization.get(room.room_id, 0) + 1
            
        for t in task.get('busy_teachers', []):
            self.faculty_busy[(t.teacher_id, ts.day, ts.slot_number)] = True
            self.teacher_day_counts[(t.teacher_id, ts.day)] = self.teacher_day_counts.get((t.teacher_id, ts.day), 0) + 1
            
        return added

    def _remove_group(self, task, window, added):
        ts = window[0]
        processed_secs_for_day_count = set()
        
        for ent in added: 
            self.entries.remove(ent)
            key = (ent['section'].class_id, ent['timeslot'].day)
            if key not in processed_secs_for_day_count:
                self.section_day_counts[key] -= 1
                processed_secs_for_day_count.add(key)

        for sub in task['sub_tasks']:
            room = sub.get('selected_room')
            if room:
                self.room_busy[(room.room_id, ts.day, ts.slot_number)] = False
                self.room_utilization[room.room_id] -= 1
            for sec in sub['sections']: self.section_busy[(sec.class_id, ts.day, ts.slot_number)] = False
            
        for t in task.get('busy_teachers', []):
            self.faculty_busy[(t.teacher_id, ts.day, ts.slot_number)] = False
            self.teacher_day_counts[(t.teacher_id, ts.day)] -= 1

    def _check_hc9(self, teacher, window, max_hours=4):
        if hasattr(self, 'iterations') and self.iterations > 10000: return True
        day = window[0].day
        slots = [ts.slot_number for ts in window]
        for s in range(1, 11):
            if s not in slots and self.faculty_busy.get((teacher.teacher_id, day, s)): slots.append(s)
        slots.sort()
        count = 1
        max_c = 1
        for j in range(1, len(slots)):
            if slots[j] == slots[j-1] + 1:
                count += 1
                max_c = max(max_c, count)
            else: count = 1
        return max_c <= max_hours

def generate_schedule(schedule_id):
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        scheduler = TimetableScheduler(schedule)
        return scheduler.generate()
    except Schedule.DoesNotExist:
        return False, f"Schedule {schedule_id} not found"