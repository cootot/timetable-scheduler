import os
import sys

sys.path.append(os.getcwd())

def test_conflicts():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'timetable_project.settings'
    import django
    django.setup()
    
    from core.models import Schedule, ScheduleEntry, Teacher, TimeSlot
    from django.db.models import Count
    
    for term in ['ODD', 'EVEN']:
        try:
            s = Schedule.objects.filter(name__icontains=term).latest('created_at')
            entries = ScheduleEntry.objects.filter(schedule=s)
            
            teacher_clashes = (
                entries.values('teacher', 'timeslot')
                .annotate(unique_courses=Count('course', distinct=True))
                .filter(unique_courses__gt=1)
            )
            
            if teacher_clashes:
                print(f"Conflicts found in {s.name}: {len(teacher_clashes)}")
                for x in teacher_clashes:
                    t = Teacher.objects.get(pk=x['teacher'])
                    ts = TimeSlot.objects.get(pk=x['timeslot'])
                    print(f" - Teacher '{t.teacher_name}' is assigned {x['unique_courses']} distinct courses at {ts.day} Slot {ts.slot_number}")
            else:
                print(f"SUCCESS: No teacher overlap conflicts found in {s.name}")
        except Exception as e:
            print(f"Failed to check {term}: {e}")

if __name__ == "__main__":
    test_conflicts()
