import os
import sys
from collections import defaultdict

sys.path.append(os.getcwd())

def verify_coverage():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'timetable_project.settings'
    import django
    django.setup()
    
    from core.models import Schedule, ScheduleEntry, Section, Teacher
    
    # We want to check the latest odd and even schedules. Let's look for "Final" in the name or just grab latest.
    for term in ['odd', 'even']:
        try:
            sched = Schedule.objects.filter(semester=term).latest('created_at')
            print(f"\n=============================================")
            print(f"VERIFICATION REPORT: {sched.name} ({sched.semester.upper()})")
            print(f"=============================================")
            
            # --- 1. SECTION COVERAGE ---
            print("\n[1] SECTION DAILY COVERAGE (Must be 5 Days: MON-FRI)")
            all_sections = Section.objects.all()
            sections_checked = 0
            sections_incomplete = []
            
            for section in all_sections:
                # We need to consider only sections that have ANY classes in this semester.
                # Year 1=Odd(1)/Even(2), Year 2=Odd(3)/Even(4), Year 3=Odd(5)/Even(6), Year 4=Odd(7)/Even(8)
                # Basically, if the section has any classes scheduled in this 'sched', check if it's 5 days.
                entries = ScheduleEntry.objects.filter(schedule=sched, section=section).select_related('timeslot')
                if entries.count() == 0:
                    continue
                
                sections_checked += 1
                days_covered = set(e.timeslot.day for e in entries)
                
                if len(days_covered) < 5:
                    missing = set(['MON', 'TUE', 'WED', 'THU', 'FRI']) - days_covered
                    sections_incomplete.append((section.class_id, list(missing)))
            
            print(f"Total active sections checked: {sections_checked}")
            if not sections_incomplete:
                print(">>> SUCCESS: 100% of active sections have at least one class EVERY DAY.")
            else:
                print(f">>> WARNING: {len(sections_incomplete)} sections are missing days!")
                for sec, missing in sections_incomplete:
                    print(f"    - Section {sec} is missing class on: {missing}")

            # --- 2. FACULTY COVERAGE ---
            print("\n[2] FACULTY DAILY COVERAGE")
            all_teachers = Teacher.objects.all()
            teachers_checked = 0
            teachers_incomplete = []
            
            for teacher in all_teachers:
                entries = ScheduleEntry.objects.filter(schedule=sched, teacher=teacher).select_related('timeslot')
                if entries.count() == 0:
                    continue
                
                teachers_checked += 1
                days_covered = set(e.timeslot.day for e in entries)
                
                if len(days_covered) < 5:
                    missing = set(['MON', 'TUE', 'WED', 'THU', 'FRI']) - days_covered
                    teachers_incomplete.append((teacher.teacher_name, list(missing)))
            
            print(f"Total active faculty checked: {teachers_checked}")
            if not teachers_incomplete:
                print(">>> SUCCESS: 100% of mapped faculty have at least one class EVERY DAY.")
            else:
                print(f">>> WARNING: {len(teachers_incomplete)} faculty are missing days.")
                # We don't fail here usually, but good to report. It's a soft constraint.
                # However, user said "this constraint should be applicable for all...".
                # If they want HARD constraint, we'll see.
                for name, missing in teachers_incomplete:
                    print(f"    - '{name}' is missing class on: {missing}")
                    
        except Exception as e:
            print(f"\nFailed to check {term} schedule. It might not exist. Error: {e}")

if __name__ == "__main__":
    verify_coverage()
