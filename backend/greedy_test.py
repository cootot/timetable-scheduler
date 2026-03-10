import os
import django
import sys

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from core.models import Schedule, Section, TimeSlot, Room
from scheduler.algorithm import TimetableScheduler, TYPE_PRACTICAL, TYPE_ADM, TYPE_LECTURE, TYPE_TUTORIAL, TYPE_PE, TYPE_FE

def run_greedy_test(schedule_id):
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
    except Schedule.DoesNotExist:
        print(f"Schedule {schedule_id} not found")
        return

    scheduler = TimetableScheduler(schedule)

    sections = list(Section.objects.all().order_by('year', 'class_id'))
    timeslots = list(TimeSlot.objects.all().order_by('day', 'slot_number'))
    all_rooms = list(Room.objects.all())
    for r in all_rooms:
        scheduler.rooms_by_type[r.room_type].append(r)

    ts_by_day = {}
    for ts in timeslots:
        ts_by_day.setdefault(ts.day, [])
        ts_by_day[ts.day].append(ts)

    scheduler._preallocate_teachers(sections)
    tasks = scheduler._build_session_tasks(sections)
    tasks.sort(key=lambda x: x['priority'])

    placed_count = 0
    unplaced = []

    for task in tasks:
        placed = False
        days = list(ts_by_day.keys())
        for day in days:
            day_slots = ts_by_day.get(day, [])
            for i in range(len(day_slots) - task['block_size'] + 1):
                window = day_slots[i : i + task['block_size']]
                
                if task.get('is_group'):
                    if scheduler._can_place_group(task, window):
                        scheduler._place_group(task, window)
                        placed = True
                        break
                else:
                    if scheduler._can_place_single(task, window):
                        scheduler._place_single(task, window)
                        placed = True
                        break
            if placed:
                break
                
        if placed:
            placed_count += 1
        else:
            unplaced.append(task)

    print(f"Total tasks: {len(tasks)}")
    print(f"Placed: {placed_count}")
    print(f"Unplaced: {len(unplaced)}")

    print("\n--- Unplaced Tasks ---")
    for t in unplaced:
        if t.get('is_group'):
            courses = [sub['course'].course_id for sub in t['sub_tasks']]
            print(f"Group Task: {t['type']} - Courses: {courses}")
        else:
            print(f"Single Task: {t['type']} - {t['course'].course_id} - Teacher: {t['teacher'].teacher_name} - Sections: {[s.class_id for s in t['sections']]}")

if __name__ == '__main__':
    run_greedy_test(6)
