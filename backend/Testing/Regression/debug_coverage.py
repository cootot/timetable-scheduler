
import os
import django
import sys
from collections import defaultdict

# Setup Django environment
sys.path.append(r'c:\Users\kkani\Documents\mainse\timetable-scheduler\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from core.models import Schedule, ScheduleEntry, Teacher, TeacherCourseMapping

def debug_coverage(semester_type):
    print(f"\n--- Debugging {semester_type.upper()} ---")
    schedule = Schedule.objects.filter(semester=semester_type).order_by('-created_at').first()
    if not schedule: return
    
    entries = ScheduleEntry.objects.filter(schedule=schedule)
    teacher_daily = defaultdict(lambda: defaultdict(int))
    teacher_total = defaultdict(int)
    for entry in entries:
        teacher_daily[entry.teacher_id][entry.timeslot.day] += 1
        teacher_total[entry.teacher_id] += 1
    
    DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI']
    for t_id, total in teacher_total.items():
        missing = [d for d in DAYS if teacher_daily[t_id][d] == 0]
        if missing and total >= 5:
            t = Teacher.objects.get(teacher_id=t_id)
            print(f"Faculty: {t.teacher_name} ({t_id}), Total Slots: {total}, Missing Days: {missing}")
            # Show what they are mapped to
            mappings = TeacherCourseMapping.objects.filter(teacher_id=t_id, course__semester=semester_type)
            print("  Mappings:")
            for m in mappings:
                print(f"    - {m.course.course_name} (Slots: {m.course.weekly_slots}, Section: {m.section_id})")

if __name__ == "__main__":
    debug_coverage('odd')
