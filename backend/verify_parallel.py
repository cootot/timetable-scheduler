import os
import sys

# Ensure backend directory is in sys.path
sys.path.append(os.getcwd())

def verify():
    # Force the correct settings module
    os.environ['DJANGO_SETTINGS_MODULE'] = 'timetable_project.settings'
    
    import django
    django.setup()
    
    from core.models import Schedule, ScheduleEntry, Course, Teacher
    from collections import defaultdict
    
    try:
        # Get the latest 'Final EVEN Coverage' schedule
        sched = Schedule.objects.filter(name='Final EVEN Coverage').latest('created_at')
        print(f"--- Verification Report: {sched.name} ({sched.semester}) ---")
        
        # 1. Check PE3 Slots
        pe3_course = Course.objects.filter(course_id='PE3').first()
        if pe3_course:
            entries = ScheduleEntry.objects.filter(schedule=sched, course=pe3_course)
            print(f"\n[1] PE3 Allocation:")
            print(f"  Total PE3 slots scheduled globally: {entries.count()}")
            # Group by section
            sec_counts = defaultdict(int)
            for e in entries:
                sec_counts[e.section.class_id] += 1
            for sec, count in sorted(sec_counts.items()):
                print(f"    - Section {sec}: {count} slots (Expected ~3)")
        else:
            print("\n[1] Error: PE3 placeholder course not found!")

        # 2. Check Teacher Daily Coverage
        print("\n[2] Faculty Daily Coverage Analysis:")
        all_teachers = Teacher.objects.all()
        coverage_stats = {'5_days': 0, '4_days': 0, 'less_than_4': 0, '0_days': 0}
        
        for teacher in all_teachers:
            entries = ScheduleEntry.objects.filter(schedule=sched, teacher=teacher).select_related('timeslot')
            if entries.count() == 0:
                coverage_stats['0_days'] += 1
                continue
                
            days_active = set()
            for e in entries:
                days_active.add(e.timeslot.day)
            
            day_count = len(days_active)
            if day_count == 5:
                coverage_stats['5_days'] += 1
            elif day_count == 4:
                coverage_stats['4_days'] += 1
            else:
                coverage_stats['less_than_4'] += 1
                
        print(f"  Total Faculty Processed: {all_teachers.count()}")
        print(f"  Faculty with classes on 5 Days: {coverage_stats['5_days']}")
        print(f"  Faculty with classes on 4 Days: {coverage_stats['4_days']}")
        print(f"  Faculty with classes on <4 Days: {coverage_stats['less_than_4']}")
        print(f"  Faculty with no classes (Not assigned/Mapped): {coverage_stats['0_days']}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    verify()
