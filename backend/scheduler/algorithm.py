"""
Core Scheduling Algorithm for M3 Timetable System
=================================================

This module implements the automated timetable generator. It acts as the 
"brain" of the application, taking all the mapping data (who teaches what to whom)
and attempting to fit it into a complex multi-dimensional grid (Time x Space x 
People x Resources) without breaking any rules.

Algorithm Approach: Priority-based Greedy with Backtracking heuristics
----------------------------------------------------------------------
1. Pre-allocation: 
   Estimates teaching loads first. Before placing any class on the calendar, 
   it assigns specific teachers to specific student sections to handle 
   resource-starvation issues ahead of time (The "Smart 4+2 Rule").

2. Phase 1 (Hard Constraint: Labs): 
   Schedules long, contiguous blocks of time (labs) first. If we schedule 
   short 1-hour theory classes first, the calendar becomes fragmented and 
   finding a 3-hour open gap for a lab becomes impossible later.

3. Phase 2 (Theory): 
   Fills in the remaining 1-hour theory slots into the gaps left around the labs.

4. Validation: 
   At every single placement attempt, it consults `ConstraintValidator` to ensure 
   no teachers are double-booked, students aren't double-booked, and rooms aren't 
   double-booked. 

Backtracking kicks in when it paints itself into a corner, though currently 
implemented as a "best-effort greedy" approach to handle college scale.

Author: Backend Team (Vamsi, Akshitha)
Sprint: 1
"""

import random
from datetime import datetime
from django.utils import timezone
from django.db import transaction

# Import the core data models we will be reading from and writing to
from core.models import (
    Schedule, ScheduleEntry, Section, Course, Teacher, Room,
    TimeSlot, TeacherCourseMapping, ConflictLog
)

# Import the constraint checker (the rule engine)
from .constraints import ConstraintValidator, calculate_schedule_quality


class TimetableScheduler:
    """
    Main stateful scheduling engine class.
    Generates conflict-free timetables using constraint programming principles.
    
    We use a class here instead of a simple function because the algorithm 
    needs to maintain complex state (like which teachers are assigned where, 
    and a running tally of conflicts) across multiple phases of generation.
    """
    
    def __init__(self, schedule):
        """
        Initialize the scheduler context.
        
        Args:
            schedule: The target Schedule database object we are populating. 
                      It acts as the parent container for all generated ScheduleEntries.
        """
        # The parent record in the database
        self.schedule = schedule
        
        # Instantiate the Rule Engine linked to this specific schedule
        self.validator = ConstraintValidator(schedule)
        
        # A list to keep track of issues we encounter but can't cleanly solve
        self.conflicts = []
        
        # A vital tracking dictionary for Phase 0 (Pre-allocation)
        # Maps a tuple of (course_id, section_class_id) to exactly 1 Teacher object
        self.teacher_assignments = {}
    
    def generate(self):
        """
        Main orchestration method for schedule generation.
        
        Crucially, this generates schedules for ALL 4 academic years simultaneously. 
        Why? Because a senior professor might teach both a 1st-year intro course 
        and a 4th-year advanced course. If we schedule year 1 first, year 4 will 
        fail because that teacher will have no free slots left.
        
        Returns:
            tuple: (success_boolean, status_message_string)
        """
        try:
            # Step 1: Lock the schedule status so the UI knows to show a spinner
            self.schedule.status = 'GENERATING'
            self.schedule.save()
            
            # Step 2: Fetch all student sections (e.g., CSE-1A, ECE-3B)
            # We group them by year so earlier years are processed systematically
            # Note: Sections exist year-round, the 'semester' field dictates the courses.
            sections = Section.objects.all().order_by('year', 'class_id')
            
            # If the database is empty, bail out gracefully
            if not sections.exists():
                return False, f"No sections found for semester {self.schedule.semester}"
            
            # Step 3: Fetch the fundamental building blocks of time (the calendar grid)
            timeslots = list(TimeSlot.objects.all().order_by('day', 'slot_number'))
            
            if not timeslots:
                return False, "No timeslots available"
            
            # Auxiliary step: Count sections by year for the final UI report
            year_counts = {}
            for section in sections:
                year_counts[section.year] = year_counts.get(section.year, 0) + 1
            
            # =========================================================
            # PHASE 0: TEACHER PRE-ALLOCATION
            # =========================================================
            # Decide exactly *who* is teaching *what* before looking at the clock.
            # This prevents us from assigning "Teacher A" to 5 sections and realizing 
            # they exceed their 40-hour max limit later on.
            self._preallocate_teachers(sections)
            
            # =========================================================
            # PHASE 1: LAB BLOCK SCHEDULING (Hard Constraint)
            # =========================================================
            # Labs require 2-3 contiguous slots (e.g., Monday 9 AM to 12 PM).
            # We must schedule these first while the timetable is completely empty.
            
            # Convert QuerySet to a standard list so we can shuffle it
            sections_list = list(sections)
            # Shuffle sections so that 'CSE-1A' doesn't always get the premium morning lab slots
            # while 'MECH-4B' always gets stuck with late Friday afternoons.
            random.shuffle(sections_list)
            
            # Iterate and place lab blocks
            for section in sections_list:
                self._schedule_section_labs(section, timeslots)

            # =========================================================
            # PHASE 2: THEORY SCHEDULING
            # =========================================================
            # Now fill in the 1-hour gaps with standard theory lectures.
            
            # Reshuffle again for fairness in theory slot distribution
            random.shuffle(sections_list)
            
            for section in sections_list:
                self._schedule_section_theory(section, timeslots)
            
            # =========================================================
            # FINALIZATION
            # =========================================================
            # Evaluate how well the algorithm did. (E.g., Did teachers get their preferred slots?)
            quality = calculate_schedule_quality(self.schedule)
            
            # Update the parent record and mark success
            self.schedule.quality_score = quality
            self.schedule.status = 'COMPLETED'
            self.schedule.completed_at = timezone.now()
            self.schedule.save()
            
            # Construct a human-readable summary of what was accomplished
            years_scheduled = ', '.join([f"Year {y}: {count} sections" for y, count in sorted(year_counts.items())])
            return True, f"Schedule generated for all years ({years_scheduled}) with quality score: {quality:.2f}"
        
        except Exception as e:
            # Catch-all failsafe to ensure the UI doesn't spin forever if a critical bug occurs
            self.schedule.status = 'FAILED'
            self.schedule.save()
            return False, f"Error during scheduling: {str(e)}"
    
    def _preallocate_teachers(self, sections):
        """
        Phase 0 execution: Pre-allocate teachers with capacity checking.
        
        This implements the "Smart 4+2 Rule" roughly adapted for generalized load balancing.
        It ensures that a highly desired teacher isn't assigned to so many sections
        that it mathematically exceeds their `max_hours_per_week`.
        """
        from collections import defaultdict
        
        # A running tally of how many hours we have promised a teacher.
        # Key: Teacher ID string. Value: Integer hours.
        teacher_load = defaultdict(int) 
        
        # Group the target students by their academic year
        sections_by_year = defaultdict(list)
        for section in sections:
            sections_by_year[section.year].append(section)
            
        # Process allocation chronologically (Year 1 up to Year 4)
        for year, year_sections in sections_by_year.items():
            
            # Find the courses relevant to this year and semester (e.g., Year 1 Odd Sem = Mechanics)
            courses = Course.objects.filter(
                year=year,
                semester=self.schedule.semester,
                is_elective=False  # Handled separately or implicitly
            )
            
            for course in courses:
                # How much time does this course take per week?
                slots_per_section = course.weekly_slots
                
                # Fetch all teachers who have indicated they *can* teach this course
                # Ordered by preference_level (5 = loves this course, 1 = hates it but can do it)
                mappings = list(TeacherCourseMapping.objects.filter(
                    course=course
                ).select_related('teacher').order_by('-preference_level'))
                
                # De-duplicate the list of allowed teachers
                distinct_teachers = []
                seen_ids = set()
                for m in mappings:
                    if m.teacher.teacher_id not in seen_ids:
                        distinct_teachers.append(m.teacher)
                        seen_ids.add(m.teacher.teacher_id)
                
                # Separate teachers into two buckets:
                # 1. Capable: They have enough free hours left to take on this section
                # 2. Overloaded: Taking this section would push them over max_hours
                capable_teachers = []
                overloaded_fallback = [] 
                
                for t in distinct_teachers:
                    current_hours = teacher_load[t.teacher_id]
                    if current_hours + slots_per_section <= t.max_hours_per_week:
                        capable_teachers.append(t)
                    else:
                        overloaded_fallback.append(t)
                
                # If mappings exist but are incomplete (not all teachers are mapped)
                is_mapped_search = (len(distinct_teachers) != Teacher.objects.count()) 
                
                # HEURISTIC TWEAK: If all the specific mapped teachers are out of hours,
                # expand our search pool to EVERY teacher in the college as a desperate fallback.
                if not capable_teachers and is_mapped_search:
                    all_teachers = Teacher.objects.all()
                    for t in all_teachers:
                        if t.teacher_id in seen_ids: continue # Already checked them
                        current = teacher_load[t.teacher_id]
                        if current + slots_per_section <= t.max_hours_per_week:
                            capable_teachers.append(t)
                
                # Sort the capable teachers by who is least busy.
                # This ensures workload is spread evenly rather than piling all work on Teacher 1.
                capable_teachers.sort(key=lambda t: teacher_load[t.teacher_id])
                
                # Also sort the overloaded list just in case we are forced to pick the "least bad" option
                overloaded_fallback.sort(key=lambda t: teacher_load[t.teacher_id])
                
                # Create a priority queue of candidates
                pool = capable_teachers + overloaded_fallback
                
                # DYNAMIC ASSIGNMENT LOOP:
                # Give each section in this year a dedicated teacher for this specific course.
                for i, section in enumerate(year_sections):
                    selected_candidate = None
                    
                    # 1. Look in our primary curated pool
                    pool.sort(key=lambda t: teacher_load[t.teacher_id])
                    
                    for cand in pool:
                        # Verify capacity once more dynamically
                        if teacher_load[cand.teacher_id] + slots_per_section <= cand.max_hours_per_week:
                            selected_candidate = cand
                            break
                    
                    # 2. If the pool is exhausted and we're desperate, do a real-time global scan
                    if not selected_candidate and is_mapped_search:
                        best_global = None
                        min_load = float('inf')  # Start with an artificially high load
                        
                        all_teachers = list(Teacher.objects.all())
                        random.shuffle(all_teachers) # Shuffle to prevent alphabetical bias
                        
                        for t in all_teachers:
                            load = teacher_load[t.teacher_id]
                            # If they have capacity
                            if load + slots_per_section <= t.max_hours_per_week:
                                # Keep track of the teacher with the absolute lowest load across college
                                if load < min_load:
                                    min_load = load
                                    best_global = t
                                    # Optimization: If they have 0 hours, grab them instantly
                                    if load == 0: break
                        
                        if best_global:
                            selected_candidate = best_global
                            # Add them to the pool so future iterations might use them too
                            pool.append(selected_candidate)
                    
                    # 3. IF EVERYTHING FAILS: We must break the rules.
                    if not selected_candidate:
                        # Pick the least heavily loaded teacher from our initial curated pool
                        # even though they will be pushed over their max_hours limit.
                        pool.sort(key=lambda t: teacher_load[t.teacher_id])
                        selected_candidate = pool[0]
                    
                    # EXECUTE: Lock in the assignment and increment their workload tracker
                    self.teacher_assignments[(course.course_id, section.class_id)] = selected_candidate
                    teacher_load[selected_candidate.teacher_id] += slots_per_section


    def _schedule_section_labs(self, section, timeslots):
        """
        Phase 1 Execution: Find contiguous blocks of time for Practical Labs.
        This is significantly harder than placing single 1-hour theory classes.
        """
        # Get courses for this specific section's year that aren't electives
        courses = Course.objects.filter(
            year=section.year,
            semester=self.schedule.semester,
            is_elective=False
        )
        
        for course in courses:
            # Determine how many consecutive hours this lab requires (e.g., 3 practicals)
            lab_slots = course.practicals if (course.is_lab or course.practicals > 0) else 0
            
            # Skip if it's purely a theory course
            if lab_slots == 0:
                continue
            
            # Lookup the teacher we assigned in Phase 0
            assignment_key = (course.course_id, section.class_id)
            teacher = self.teacher_assignments.get(assignment_key)
            
            # Safety fallback if pre-allocation failed somehow
            if not teacher:
                mappings = TeacherCourseMapping.objects.filter(course=course).order_by('-preference_level')
                if mappings.exists():
                    teacher = mappings.first().teacher
                else:
                    # Very bad: No teacher in database can teach this course
                    self._log_conflict('NO_TEACHER', f"No teacher for {course.course_id} (Lab)", 'HIGH')
                    continue

            block_assigned = False
            
            # A dictionary grouping slots by Day. 
            # E.g.: {'MON': [Slot1, Slot2...], 'TUE': [Slot1, Slot2...]}
            slots_by_day = {}
            for ts in timeslots:
                if ts.day not in slots_by_day:
                    slots_by_day[ts.day] = []
                slots_by_day[ts.day].append(ts)
            
            # Randomize the days so labs don't clump on Mondays
            days = list(slots_by_day.keys())
            random.shuffle(days)
            
            for day in days:
                # Ensure slots are in chronological order (Slot 1, then Slot 2...)
                day_slots = sorted(slots_by_day[day], key=lambda x: x.slot_number)
                
                # Sliding Window Algorithm to find sequential slots
                # E.g., if lab_slots=3, check [Slot 1, 2, 3], then [Slot 2, 3, 4]
                for i in range(len(day_slots) - lab_slots + 1):
                    # Extract the potential slice of time
                    window = day_slots[i : i + lab_slots]
                    
                    # Sanity Check: Ensure slots are actually consecutive.
                    # e.g., slot 3 and slot 5 are not a valid 2-hour lab block
                    is_continuous = True
                    for k in range(len(window) - 1):
                        if window[k+1].slot_number != window[k].slot_number + 1:
                            is_continuous = False
                            break
                    
                    # If there's a gap (like lunch break), skip this window
                    if not is_continuous: continue

                    # Evaluate if the Teacher and Section are both completely free during the entire window
                    if self._can_schedule_block(window, section, course, teacher):
                         
                         # If free, try to secure a physical Laboratory room for the block
                         valid_room = self._find_block_room(window, course)
                         
                         if valid_room:
                             # SUCCESS: Write entries to database for each hour of the lab
                             for ts in window:
                                 ScheduleEntry.objects.create(
                                     schedule=self.schedule,
                                     section=section,
                                     course=course,
                                     teacher=teacher,
                                     room=valid_room,
                                     timeslot=ts,
                                     is_lab_session=True
                                 )
                             block_assigned = True
                             
                             # Critical: Reinstantiate validator so it "sees" the new entries immediately
                             # This prevents the next lab from double-booking this teacher.
                             self.validator = ConstraintValidator(self.schedule)
                             break # Exit window sliding loop
                
                if block_assigned: break # Exit day checking loop
            
            if not block_assigned:
                # If we checked every day and every window and couldn't fit the lab, flag an error
                self._log_conflict('LAB_BLOCK_FAILED', f"Failed to assign lab block for {course.course_id}", 'HIGH')

    def _schedule_section_theory(self, section, timeslots):
        """
        Phase 2 Execution: Fill in remaining required hours with theory lectures.
        Because these are typically 1-hour slots, they are easier to fit into gaps.
        """
        courses = Course.objects.filter(
            year=section.year,
            semester=self.schedule.semester,
            is_elective=False
        )
        
        for course in courses:
            # 1. Count how much of this course was already scheduled in Phase 1
            # E.g., Physics requires 5 slots. If 2 went to a lab, we need 3 theories.
            current_slots = ScheduleEntry.objects.filter(
                schedule=self.schedule,
                section=section,
                course=course
            ).count()
            
            # Calculate remaining delta
            needed = course.weekly_slots - current_slots
            if needed <= 0:
                continue # Course is fully scheduled
            
            # Lookup preassigned teacher
            assignment_key = (course.course_id, section.class_id)
            teacher = self.teacher_assignments.get(assignment_key)
            
            if not teacher:
                mappings = TeacherCourseMapping.objects.filter(course=course).order_by('-preference_level')
                if mappings.exists():
                    teacher = mappings.first().teacher
                else:
                    self._log_conflict('NO_TEACHER', f"No teacher for {course.course_id}", 'HIGH')
                    continue
            
            slots_scheduled = 0
            
            # Shuffle timeslots to distribute classes organically across the week
            # instead of front-loading early Monday mornings.
            available_slots = list(timeslots)
            random.shuffle(available_slots)
            
            # Iterate through the random schedule
            for timeslot in available_slots:
                # Stop if we hit our quota
                if slots_scheduled >= needed:
                    break
                
                # Check for a free Theory room first (inexpensive query)
                room = self._find_suitable_room(course, timeslot)
                if not room: continue
                
                # Final intensive validation check (Are teacher/student engaged? Max classes reached?)
                is_valid, _ = self.validator.validate_all(section, course, teacher, room, timeslot)
                if is_valid:
                    # Write to database
                    ScheduleEntry.objects.create(
                        schedule=self.schedule,
                        section=section,
                        course=course,
                        teacher=teacher,
                        room=room,
                        timeslot=timeslot,
                        is_lab_session=False
                    )
                    slots_scheduled += 1
                    # Update local rule engine state
                    self.validator = ConstraintValidator(self.schedule)
            
    def _can_schedule_block(self, window, section, course, teacher):
        """
        Helper method for Lab Scheduling. 
        Checks if a continuous block of time is conflict-free for the human actors.
        
        Args:
            window: List of consecutive TimeSlot objects
            section: Section object (The students)
            course: Course object
            teacher: Teacher object (The faculty member)
            
        Returns: True if both teacher and students are entirely free during the window.
        """
        for ts in window:
            # Check if teacher has another class at this specific hour
            t_valid, _ = self.validator.validate_faculty_availability(teacher, ts)
            if not t_valid: return False
            
            # Check if students have another class at this specific hour
            s_valid, _ = self.validator.validate_section_availability(section, ts)
            if not s_valid: return False
            
        return True

    def _find_block_room(self, window, course):
        """
        Helper method for Lab Scheduling.
        Finds a physical room that is vacant for the ENTIRE continuous duration of a lab.
        
        Args:
            window: List of consecutive TimeSlot objects
            course: Determines whether it needs a LAB or CLASSROOM
        """
        # Determine strict room requirements based on course properties
        room_type = 'LAB' if (course.is_lab or course.practicals > 0) else 'CLASSROOM'
        rooms = list(Room.objects.filter(room_type=room_type))
        random.shuffle(rooms) # Prevent packing all labs into Lab 1
        
        for room in rooms:
            available = True
            # Verify the room is empty for every hour of the required block
            for ts in window:
                r_valid, _ = self.validator.validate_room_availability(room, ts)
                if not r_valid:
                    available = False
                    break # Room is busy at least one hour, break loop early
            
            # If we made it through the inner loop without breaking, the room is perfect
            if available:
                return room
                
        # No rooms in the entire college can support this contiguous block
        return None
    
    def _find_suitable_room(self, course, timeslot):
        """
        Helper method for Theory Scheduling.
        Find a single suitable CLASSROOM for a 1-hour session.
        This method is strictly for Phase 2.
        
        Args:
            course: Course object
            timeslot: Single TimeSlot object
        
        Returns:
            Room object or None if college is out of space.
        """
        # Theory sessions ALWAYS require standard classrooms,
        # Therefore we hardcode filtering to 'CLASSROOM'
        rooms = list(Room.objects.filter(room_type='CLASSROOM'))
        random.shuffle(rooms) # Prevent overloading Room 101
        
        for room in rooms:
            # Check if room is double booked
            is_valid, _ = self.validator.validate_room_availability(room, timeslot)
            if is_valid:
                return room
        
        return None
    
    def _log_conflict(self, conflict_type, description, severity):
        """
        Centralized error reporter.
        Writes unresolved algorithmic blockers to the database so administrators
        can review them later in the UI (e.g., "Why didn't CSE-1A get physics?").
        
        Args:
            conflict_type: Short error code string
            description: Detailed human-readable explanation
            severity: String enum (LOW, MEDIUM, HIGH, CRITICAL)
        """
        ConflictLog.objects.create(
            schedule=self.schedule,
            conflict_type=conflict_type,
            description=description,
            severity=severity
        )
        # Also store locally so the class instance can report it easily
        self.conflicts.append(description)


def generate_schedule(schedule_id):
    """
    Utility wrapper function.
    Provides a simple functional entry point to start the complex class-based generation.
    Often called via async tasks (like Celery) or management commands.
    
    Args:
        schedule_id: Integer primary key for the target Schedule in database.
    
    Returns:
        tuple: (success_boolean, status_message)
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        scheduler = TimetableScheduler(schedule)
        return scheduler.generate()
    except Schedule.DoesNotExist:
        return False, f"Schedule with ID {schedule_id} not found"
