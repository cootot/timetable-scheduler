import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from core.models import Teacher, Course, Room, Section

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username='admin', role='ADMIN')

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(username='faculty', role='FACULTY')

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestResourcePermissions:
    """Tests for role-based access to core resources (Read all, Write HOD/Admin)"""

    def test_teacher_read_access_faculty(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        response = api_client.get('/api/teachers/')
        assert response.status_code == status.HTTP_200_OK

    def test_teacher_create_denied_faculty(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        data = {"teacher_id": "T99", "teacher_name": "Test", "email": "a@b.com", "department": "CSE", "max_hours_per_week": 20}
        response = api_client.post('/api/teachers/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_course_read_access_faculty(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        response = api_client.get('/api/courses/')
        assert response.status_code == status.HTTP_200_OK

    def test_room_create_denied_faculty(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        data = {"room_id": "R99", "block": "A", "floor": 1, "room_type": "CLASSROOM"}
        response = api_client.post('/api/rooms/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_section_read_access_faculty(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        response = api_client.get('/api/sections/')
        assert response.status_code == status.HTTP_200_OK
