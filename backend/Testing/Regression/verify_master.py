
import os
import django
import sys
from collections import defaultdict

# Setup Django environment
sys.path.append(r'c:\Users\kkani\Documents\mainse\timetable-scheduler\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from core.models import Schedule, ScheduleEntry, Teacher, TimeSlot
from scheduler.algorithm import generate_schedule

DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']

def verify_master(semester_type):
    print(f"\n--- Master Verification: {semester_type.upper()} Semester ---")
    
    schedule, created = Schedule.objects.get_or_create(
        name=f"Master Test {semester_type.capitalize()}",
        semester=semester_type,
        defaults={'status': 'PENDING'}
    )
    
    print(f"Generating timetable for {schedule.name}...")
    success, message = generate_schedule(schedule.schedule_id)
    print(f"Result: {message}")
    
    entries = ScheduleEntry.objects.filter(schedule=schedule)
    teacher_daily = defaultdict(lambda: defaultdict(int))
    teacher_total = defaultdict(int)
    room_conflicts = 0
    
    for entry in entries:
        t_id = entry.teacher.teacher_id
        day = entry.timeslot.day
        teacher_daily[t_id][day] += 1
        teacher_total[t_id] += 1
        
        # Check room conflict
        is_lab_course = "PRACTICAL" in entry.session_type or "LAB" in entry.session_type
        is_lab_room = entry.room.room_type == 'LAB'
        if not is_lab_course and is_lab_room:
            room_conflicts += 1
            
    teachers = set(t[0] for t in entries.values_list('teacher_id'))
    coverage_failures = 0
    workload_summary = []
    
    for t_id in sorted(teachers):
        total = teacher_total[t_id]
        missing_days = [d for d in DAYS if teacher_daily[t_id][d] == 0]
        
        # Daily coverage requirement for any teacher with 5+ slots
        if total >= 5 and missing_days:
            coverage_failures += 1
            # print(f"  Coverage Fail: {t_id} (Slots: {total}) Missing: {missing_days}")
            
        t_obj = Teacher.objects.get(teacher_id=t_id)
        limit = t_obj.max_hours_per_week
        pct = (total / limit * 100) if limit > 0 else 0
        workload_summary.append(pct)
        
    print(f"Total Faculty: {len(teachers)}")
    print(f"Daily Coverage Gaps (Faculty >= 5 slots): {coverage_failures}")
    print(f"Room Conflicts (Theory in Lab): {room_conflicts}")
    if workload_summary:
        print(f"Workload %: Avg {sum(workload_summary)/len(workload_summary):.1f}%, Min {min(workload_summary):.1f}%, Max {max(workload_summary):.1f}%")

if __name__ == "__main__":
    verify_master('odd')
    verify_master('even')
