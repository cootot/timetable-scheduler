
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

def verify_workload(semester_type):
    print(f"\n--- Verifying {semester_type.upper()} Semester ---")
    
    # Get or create a schedule
    schedule, created = Schedule.objects.get_or_create(
        name=f"Workload Test {semester_type.capitalize()}",
        semester=semester_type,
        defaults={'status': 'PENDING'}
    )
    
    print(f"Generating timetable for {schedule.name}...")
    success, message = generate_schedule(schedule.schedule_id)
    print(f"Result: {message}")
    
    if not success:
        return False

    entries = ScheduleEntry.objects.filter(schedule=schedule)
    teacher_daily = defaultdict(lambda: defaultdict(int))
    teacher_total = defaultdict(int)
    
    for entry in entries:
        t_id = entry.teacher.teacher_id
        day = entry.timeslot.day
        teacher_daily[t_id][day] += 1
        teacher_total[t_id] += 1
        
    teachers = set(t[0] for t in entries.values_list('teacher_id'))
    
    coverage_issues = 0
    workload_summary = []
    
    for t_id in sorted(teachers):
        missing_days = [d for d in DAYS if teacher_daily[t_id][d] == 0]
        total = teacher_total[t_id]
        
        t_obj = Teacher.objects.get(teacher_id=t_id)
        limit = t_obj.max_hours_per_week
        pct = (total / limit * 100) if limit > 0 else 0
        
        if missing_days:
            # Only count as issue if they have enough total hours to potentially cover all days
            if total >= 5:
                # print(f"ISSUE: Faculty {t_id} missing classes on {missing_days} (Total: {total})")
                coverage_issues += 1
        
        workload_summary.append(pct)
        
    print(f"Total faculty scheduled: {len(teachers)}")
    print(f"Faculty with daily coverage issues: {coverage_issues}")
    if workload_summary:
        print(f"Avg Workload %: {sum(workload_summary)/len(workload_summary):.1f}%")
        print(f"Min Workload %: {min(workload_summary):.1f}%")
        print(f"Max Workload %: {max(workload_summary):.1f}%")
    
    return coverage_issues == 0

if __name__ == "__main__":
    verify_workload('odd')
    verify_workload('even')
