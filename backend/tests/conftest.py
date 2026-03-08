import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from core.models import Teacher, Room, Course, Section, TimeSlot, Schedule
from django.conf import settings

User = get_user_model()

@pytest.fixture(autouse=True)
def _mock_email_backend(settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(
        username='admin_test',
        password='password123',
        email='admin@test.com',
        role='ADMIN'
    )
    return user

@pytest.fixture
def faculty_user(db):
    user = User.objects.create_user(
        username='faculty_test',
        password='password123',
        email='faculty@test.com',
        role='FACULTY'
    )
    return user

@pytest.fixture
def unauthorized_user(db):
    user = User.objects.create_user(
        username='student_test',
        password='password123',
        email='student@test.com',
        role='STUDENT' # Assuming STUDENT role exists or just a non-privileged user
    )
    return user

@pytest.fixture
def sample_data(db):
    # Create basic data needed for schedule generation
    teacher = Teacher.objects.create(
        teacher_id='T001',
        teacher_name='John Doe',
        email='john@test.com',
        department='CSE',
        max_hours_per_week=20
    )
    
    room = Room.objects.create(
        room_id='R101',
        block='A',
        floor=1,
        room_type='CLASSROOM'
    )
    
    course = Course.objects.create(
        course_id='CSE101',
        course_name='Intro to CS',
        year=1,
        semester='odd',
        lectures=3,
        theory=3,
        practicals=0,
        credits=3,
        weekly_slots=3
    )
    
    section = Section.objects.create(
        class_id='CSE1A',
        year=1,
        section='A',
        department='CSE'
    )
    
    # Create some timeslots
    TimeSlot.objects.create(
        slot_id='MON1',
        day='MON',
        slot_number=1,
        start_time='09:00',
        end_time='10:00'
    )
    
    return {
        'teacher': teacher,
        'room': room,
        'course': course,
        'section': section
    }

@pytest.fixture
def generated_schedule(db):
    schedule = Schedule.objects.create(
        name='Test Schedule',
        semester='odd',
        year=1,
        status='COMPLETED'
    )
    return schedule
