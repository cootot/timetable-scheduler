import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')
django.setup()

from core.models import User, Teacher, Schedule, ScheduleEntry, Notification, TimeSlot, Course, Room, Section
from scheduler.views import publish_schedule
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.request import Request
from django.core import mail

def run_test():
    from django.conf import settings
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    # Cleanup previous runs
    User.objects.filter(username__in=["t1", "t2", "admin_test"]).delete()
    Teacher.objects.filter(teacher_id__in=["T1", "T2"]).delete()
    Schedule.objects.filter(name__startswith="Sch ").delete()
    
    # Setup users and teachers
    user1, _ = User.objects.get_or_create(username="t1", email="t1@example.com", is_staff=True)
    teacher1, _ = Teacher.objects.get_or_create(teacher_id="T1", defaults={"teacher_name": "Teacher 1", "email": "t1@example.com", "max_hours_per_week": 20})
    user1.teacher = teacher1
    user1.save()

    user2, _ = User.objects.get_or_create(username="t2", email="t2@example.com", is_staff=True)
    teacher2, _ = Teacher.objects.get_or_create(teacher_id="T2", defaults={"teacher_name": "Teacher 2", "email": "t2@example.com", "max_hours_per_week": 20})
    user2.teacher = teacher2
    user2.save()

    # Pre-requisites
    ts1, _ = TimeSlot.objects.get_or_create(day="MON", slot_number=1, defaults={"start_time": "09:00", "end_time": "10:00"})
    ts2, _ = TimeSlot.objects.get_or_create(day="TUE", slot_number=2, defaults={"start_time": "10:00", "end_time": "11:00"})
    c1, _ = Course.objects.get_or_create(course_id="C1", defaults={"course_name": "Course 1", "year": 1, "semester": "odd", "lectures": 3, "theory": 0, "practicals": 0, "credits": 3, "weekly_slots": 3})
    r1, _ = Room.objects.get_or_create(room_id="R1", defaults={"room_type": "CLASSROOM", "block": "A", "floor": 1})
    s1, _ = Section.objects.get_or_create(class_id="S1", defaults={"department": "CSE", "year": 1, "section": "A"})

    admin_user, _ = User.objects.get_or_create(username="admin_test", is_superuser=True)

    s2, _ = Section.objects.get_or_create(class_id="S2", defaults={"department": "CSE", "year": 1, "section": "B"})
    
    # 1. Create first schedule
    sch1 = Schedule.objects.create(name="Sch 1", semester=1, year=2024, status="COMPLETED")
    
    ScheduleEntry.objects.create(schedule=sch1, teacher=teacher1, timeslot=ts1, course=c1, room=r1, section=s1)
    ScheduleEntry.objects.create(schedule=sch1, teacher=teacher2, timeslot=ts2, course=c1, room=r1, section=s2)

    from rest_framework.test import APIClient
    from rest_framework_simplejwt.tokens import RefreshToken
    admin_user.role = 'ADMIN'
    admin_user.save()
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    # Empty outbox
    mail.outbox = []
    
    print("Publishing Sch 1...")
    response = client.post(f'/api/scheduler/publish/{sch1.schedule_id}/', SERVER_NAME='localhost')
    print("Publish Sch 1 Response:", response.content)
    
    print("Emails sent:", len(mail.outbox))
    print("Notifications count T1:", Notification.objects.filter(recipient=user1).count())
    print("Notifications count T2:", Notification.objects.filter(recipient=user2).count())

    ts3, _ = TimeSlot.objects.get_or_create(day="WED", slot_number=3, defaults={"start_time": "11:00", "end_time": "12:00"})

    # 2. Create second schedule (T1 schedule changes, T2 schedule doesn't)
    sch2 = Schedule.objects.create(name="Sch 2", semester=1, year=2024, status="COMPLETED")
    
    # T1 moves to ts3
    ScheduleEntry.objects.create(schedule=sch2, teacher=teacher1, timeslot=ts3, course=c1, room=r1, section=s1)
    # T2 remains at ts2
    s2, _ = Section.objects.get_or_create(class_id="S2", defaults={"department": "CSE", "year": 1, "section": "B"})
    ScheduleEntry.objects.create(schedule=sch2, teacher=teacher2, timeslot=ts2, course=c1, room=r1, section=s2)

    # Empty outbox
    mail.outbox = []
    Notification.objects.all().delete()

    print("\nPublishing Sch 2...")
    response = client.post(f'/api/scheduler/publish/{sch2.schedule_id}/', SERVER_NAME='localhost')
    print("Publish Sch 2 Response:", response.content)

    print("Emails sent:", len(mail.outbox))
    for email in mail.outbox:
        print(f"Email To: {email.to}, Subject: {email.subject}, Body:\\n{email.body}\\n---")

    print(f"Notifications T1 (changed): {Notification.objects.filter(recipient=user1).count()}")
    for n in Notification.objects.filter(recipient=user1):
        print(f"  T1 Notif: {n.message}")
        
    print(f"Notifications T2 (unchanged): {Notification.objects.filter(recipient=user2).count()}")
    for n in Notification.objects.filter(recipient=user2):
        print(f"  T2 Notif: {n.message}")

if __name__ == "__main__":
    run_test()
