import os
import sys
from collections import defaultdict

sys.path.append(os.getcwd())

def verify():
    os.environ['DJANGO_SETTINGS_MODULE'] = 'timetable_project.settings'
    import django
    django.setup()
    
    from core.models import Schedule, ScheduleEntry, Course
    
    for term in ['ODD', 'EVEN']:
        try:
            sched = Schedule.objects.filter(name=f'Final Sync Phase {term}').latest('created_at')
            print(f"\n--- Verification Report: {sched.name} ({sched.semester}) ---")
            
            phases = Course.objects.filter(course_name__icontains='Project Phase')
            for p in phases:
                entries = ScheduleEntry.objects.filter(schedule=sched, course=p).select_related('section', 'timeslot')
                if not entries.exists():
                    continue
                    
                # Group by timeslot to see which sections are sharing it
                slot_map = defaultdict(list)
                for e in entries:
                    slot_str = f"{e.timeslot.day} Slot {e.timeslot.slot_number}"
                    slot_map[slot_str].append(e.section.class_id)
                
                print(f"\n{p.course_name} ({p.course_id}):")
                for slot, secs in sorted(slot_map.items()):
                    print(f"  {slot}: {sorted(secs)}")
                    
        except Exception as e:
            print(f"Failed to check {term}: {e}")

if __name__ == "__main__":
    verify()
