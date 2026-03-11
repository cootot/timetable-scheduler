
import os
import django
import sys

# Setup Django environment
sys.path.append(r'c:\Users\kkani\Documents\mainse\timetable-scheduler\backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from core.models import Schedule, ScheduleEntry, Room, ConflictLog
from scheduler.algorithm import generate_schedule

def verify_semester(semester_type):
    print(f"\n--- Verifying {semester_type.upper()} Semester ---")
    
    # Get or create a schedule for testing
    schedule, created = Schedule.objects.get_or_create(
        name=f"Test {semester_type.capitalize()} Semester",
        semester=semester_type,
        defaults={'status': 'PENDING'}
    )
    
    print(f"Generating timetable for {schedule.name}...")
    success, message = generate_schedule(schedule.schedule_id)
    print(f"Result: {message}")
    
    if not success:
        print("Generation failed. Check logs.")
        return False

    # Check for Theory-in-Lab conflicts
    entries = ScheduleEntry.objects.filter(schedule=schedule)
    conflicts_found = 0
    
    # Practical sessions can be in LAB or CLASSROOM (sometimes labs are full, but it's preferred)
    # Theory sessions MUST NOT be in LAB
    
    for entry in entries:
        is_theory = not entry.is_lab_session
        is_lab_room = entry.room.room_type == 'LAB'
        
        if is_theory and is_lab_room:
            print(f"CONFLICT: Theory session '{entry.course.course_name}' (Year {entry.section.year}) assigned to Lab Room '{entry.room.room_id}'")
            conflicts_found += 1
            
    # Check ConflictLog
    unresolved_conflicts = ConflictLog.objects.filter(schedule=schedule, resolved=False).count()
    
    print(f"Theory-in-Lab conflicts found: {conflicts_found}")
    print(f"Unresolved entries in ConflictLog: {unresolved_conflicts}")
    
    return conflicts_found == 0

if __name__ == "__main__":
    odd_ok = verify_semester('odd')
    even_ok = verify_semester('even')
    
    if odd_ok and even_ok:
        print("\nSUCCESS: All theory sessions are correctly assigned!")
        sys.exit(0)
    else:
        print("\nFAILURE: Some theory sessions are still in lab rooms.")
        sys.exit(1)
