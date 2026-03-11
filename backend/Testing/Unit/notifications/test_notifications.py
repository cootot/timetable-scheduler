"""
Tests for the Notification system — publish endpoint & notification APIs.

Uses existing pytest+DRF patterns from conftest.py.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from core.models import (
    Teacher, Room, Course, Section, TimeSlot,
    Schedule, ScheduleEntry, Notification,
)

User = get_user_model()


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_notif',
        password='password123',
        email='admin_notif@test.com',
        role='ADMIN',
    )


@pytest.fixture
def faculty_user(db, teacher_a):
    """Faculty user linked to teacher_a (auto-created by Teacher post_save signal)."""
    return User.objects.get(teacher=teacher_a)


@pytest.fixture
def faculty_user_b(db, teacher_b):
    """Faculty user linked to teacher_b (auto-created by Teacher post_save signal)."""
    return User.objects.get(teacher=teacher_b)


@pytest.fixture
def teacher_a(db):
    return Teacher.objects.create(
        teacher_id='TA01',
        teacher_name='Alice',
        email='alice@test.com',
        department='CSE',
        max_hours_per_week=20,
    )


@pytest.fixture
def teacher_b(db):
    return Teacher.objects.create(
        teacher_id='TB02',
        teacher_name='Bob',
        email='bob@test.com',
        department='CSE',
        max_hours_per_week=20,
    )


@pytest.fixture
def room(db):
    return Room.objects.create(
        room_id='R101', block='A', floor=1, room_type='CLASSROOM',
    )


@pytest.fixture
def room_b(db):
    return Room.objects.create(
        room_id='R102', block='A', floor=1, room_type='CLASSROOM',
    )


@pytest.fixture
def course(db):
    return Course.objects.create(
        course_id='CS101', course_name='Intro CS',
        year=1, semester='odd', lectures=3, theory=3,
        practicals=0, credits=3, weekly_slots=3,
    )


@pytest.fixture
def section(db):
    return Section.objects.create(
        class_id='CSE1A', year=1, section='A', department='CSE',
    )


@pytest.fixture
def section_b(db):
    return Section.objects.create(
        class_id='CSE1B', year=1, section='B', department='CSE',
    )


@pytest.fixture
def timeslot_mon1(db):
    return TimeSlot.objects.create(
        slot_id='MON1', day='MON', slot_number=1,
        start_time='09:00', end_time='10:00',
    )


@pytest.fixture
def timeslot_mon2(db):
    return TimeSlot.objects.create(
        slot_id='MON2', day='MON', slot_number=2,
        start_time='10:00', end_time='11:00',
    )


@pytest.fixture
def schedule_with_entries(db, teacher_a, teacher_b, room, room_b, course, section, section_b, timeslot_mon1, timeslot_mon2):
    """A COMPLETED schedule with two entries: one for each teacher."""
    schedule = Schedule.objects.create(
        name='Test Schedule 1', semester='odd', year=1, status='COMPLETED',
    )
    ScheduleEntry.objects.create(
        schedule=schedule, section=section, course=course,
        teacher=teacher_a, room=room, timeslot=timeslot_mon1,
    )
    ScheduleEntry.objects.create(
        schedule=schedule, section=section_b, course=course,
        teacher=teacher_b, room=room_b, timeslot=timeslot_mon2,
    )
    return schedule


# ─── Notification Model Tests ─────────────────────────────────────────────────

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestNotificationModel:
    def test_notification_creation(self, admin_user, schedule_with_entries):
        notif = Notification.objects.create(
            recipient=admin_user,
            schedule=schedule_with_entries,
            title='Test Notification',
            message='Hello, world!',
        )
        assert notif.is_read is False
        assert notif.created_at is not None
        assert 'Test Notification' in str(notif)

    def test_notification_ordering(self, admin_user):
        n1 = Notification.objects.create(recipient=admin_user, title='First', message='msg')
        n2 = Notification.objects.create(recipient=admin_user, title='Second', message='msg')
        notifs = list(Notification.objects.filter(recipient=admin_user))
        assert notifs[0].id == n2.id  # newest first


# ─── Publish Endpoint Tests ───────────────────────────────────────────────────

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestPublishSchedule:
    def test_publish_first_schedule_notifies_all(
        self, api_client, admin_user, faculty_user, faculty_user_b,
        schedule_with_entries,
    ):
        """First publish should notify all teachers in the schedule."""
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(f'/api/scheduler/publish/{schedule_with_entries.schedule_id}/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'published'
        assert resp.data['notifications_sent'] == 2

        schedule_with_entries.refresh_from_db()
        assert schedule_with_entries.status == 'PUBLISHED'

        # Both faculty users should have a notification
        assert Notification.objects.filter(recipient=faculty_user).count() == 1
        assert Notification.objects.filter(recipient=faculty_user_b).count() == 1

    def test_publish_detects_changes(
        self, api_client, admin_user, faculty_user, faculty_user_b,
        schedule_with_entries, teacher_a, teacher_b, room, room_b, course, section, section_b,
        timeslot_mon1, timeslot_mon2,
    ):
        """Publishing a second schedule should only notify teachers with changes."""
        # First: publish the initial schedule
        api_client.force_authenticate(user=admin_user)
        api_client.post(f'/api/scheduler/publish/{schedule_with_entries.schedule_id}/')

        # Create a second schedule — same entries for teacher_b, different for teacher_a
        sched2 = Schedule.objects.create(
            name='Test Schedule 2', semester='odd', year=1, status='COMPLETED',
        )
        # Teacher A now has slot 2 instead of slot 1 — this is a change
        ScheduleEntry.objects.create(
            schedule=sched2, section=section, course=course,
            teacher=teacher_a, room=room, timeslot=timeslot_mon2,
        )
        # Teacher B still has slot 2 in room_b / section_b — same as before
        ScheduleEntry.objects.create(
            schedule=sched2, section=section_b, course=course,
            teacher=teacher_b, room=room_b, timeslot=timeslot_mon2,
        )

        resp = api_client.post(f'/api/scheduler/publish/{sched2.schedule_id}/')
        assert resp.status_code == 200
        assert resp.data['status'] == 'published'

        # Only teacher_a changed (slot 1 → slot 2), teacher_b unchanged
        assert resp.data['notifications_sent'] == 1

        # Teacher A should have 2 notifications total (one from each publish)
        assert Notification.objects.filter(recipient=faculty_user).count() == 2
        # Teacher B had 1 from first publish, none from second
        assert Notification.objects.filter(recipient=faculty_user_b).count() == 1

    def test_publish_requires_completed_status(self, api_client, admin_user, db):
        """Cannot publish a PENDING or FAILED schedule."""
        schedule = Schedule.objects.create(
            name='Pending', semester='odd', year=1, status='PENDING',
        )
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(f'/api/scheduler/publish/{schedule.schedule_id}/')
        assert resp.status_code == 400
        assert 'Cannot publish' in resp.data['error']

    def test_publish_not_found(self, api_client, admin_user):
        """Publishing a non-existent schedule returns 404."""
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post('/api/scheduler/publish/99999/')
        assert resp.status_code == 404

    def test_publish_requires_auth(self, api_client, schedule_with_entries):
        """Unauthenticated users cannot publish."""
        resp = api_client.post(f'/api/scheduler/publish/{schedule_with_entries.schedule_id}/')
        assert resp.status_code == 401


# ─── Notification API Tests ───────────────────────────────────────────────────

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestNotificationAPI:
    def test_list_only_own_notifications(self, api_client, faculty_user, faculty_user_b):
        """Users should only see their own notifications."""
        Notification.objects.create(recipient=faculty_user, title='For A', message='msg')
        Notification.objects.create(recipient=faculty_user_b, title='For B', message='msg')

        api_client.force_authenticate(user=faculty_user)
        resp = api_client.get('/api/notifications/')
        data = resp.data if isinstance(resp.data, list) else resp.data.get('results', resp.data)
        assert len(data) == 1
        assert data[0]['title'] == 'For A'

    def test_mark_read(self, api_client, faculty_user):
        """mark_read should set is_read to True."""
        notif = Notification.objects.create(recipient=faculty_user, title='Test', message='msg')
        api_client.force_authenticate(user=faculty_user)
        resp = api_client.post(f'/api/notifications/{notif.id}/mark_read/')
        assert resp.status_code == 200
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_mark_all_read(self, api_client, faculty_user):
        """mark_all_read should mark all notifications as read."""
        Notification.objects.create(recipient=faculty_user, title='N1', message='msg')
        Notification.objects.create(recipient=faculty_user, title='N2', message='msg')
        api_client.force_authenticate(user=faculty_user)
        resp = api_client.post('/api/notifications/mark_all_read/')
        assert resp.status_code == 200
        assert resp.data['count'] == 2
        assert Notification.objects.filter(recipient=faculty_user, is_read=False).count() == 0

    def test_unread_count(self, api_client, faculty_user):
        """unread_count should return the correct number."""
        Notification.objects.create(recipient=faculty_user, title='N1', message='m')
        Notification.objects.create(recipient=faculty_user, title='N2', message='m', is_read=True)
        Notification.objects.create(recipient=faculty_user, title='N3', message='m')

        api_client.force_authenticate(user=faculty_user)
        resp = api_client.get('/api/notifications/unread_count/')
        assert resp.status_code == 200
        assert resp.data['count'] == 2
