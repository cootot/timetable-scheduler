import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from accounts.permissions import IsAdmin, IsHODOrAdmin, IsFacultyOrAbove

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_test',
        email='admin@test.com',
        password='password123',
        role='ADMIN'
    )

@pytest.fixture
def hod_user(db):
    return User.objects.create_user(
        username='hod_test',
        email='hod@test.com',
        password='password123',
        role='HOD',
        department='CSE'
    )

@pytest.fixture
def faculty_user(db):
    return User.objects.create_user(
        username='faculty_test',
        email='faculty@test.com',
        password='password123',
        role='FACULTY',
        department='CSE'
    )

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestRBACPermissions:
    """Tests for custom permission classes logic"""

    def test_is_admin_permission(self, admin_user, hod_user, faculty_user):
        permission = IsAdmin()
        assert permission.has_permission(type('Request', (), {'user': admin_user})(), None) is True
        assert permission.has_permission(type('Request', (), {'user': hod_user})(), None) is False
        assert permission.has_permission(type('Request', (), {'user': faculty_user})(), None) is False

    def test_is_hod_or_admin_permission(self, admin_user, hod_user, faculty_user):
        permission = IsHODOrAdmin()
        assert permission.has_permission(type('Request', (), {'user': admin_user})(), None) is True
        assert permission.has_permission(type('Request', (), {'user': hod_user})(), None) is True
        assert permission.has_permission(type('Request', (), {'user': faculty_user})(), None) is False

    def test_is_faculty_or_above_permission(self, admin_user, hod_user, faculty_user):
        permission = IsFacultyOrAbove()
        assert permission.has_permission(type('Request', (), {'user': admin_user})(), None) is True
        assert permission.has_permission(type('Request', (), {'user': hod_user})(), None) is True
        assert permission.has_permission(type('Request', (), {'user': faculty_user})(), None) is True

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestUserAuthEndpoints:
    """Tests for User authentication and profile endpoints"""

    def test_profile_access(self, api_client, faculty_user):
        api_client.force_authenticate(user=faculty_user)
        response = api_client.get('/api/auth/me/')
        assert response.status_code == status.HTTP_200_OK

    def test_admin_user_management_access(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        response = api_client.get('/api/auth/users/')
        assert response.status_code == status.HTTP_200_OK

    def test_hod_user_management_denied(self, api_client, hod_user):
        api_client.force_authenticate(user=hod_user)
        response = api_client.get('/api/auth/users/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_protected_account_deletion_restriction(self, api_client, admin_user):
        protected_user = User.objects.create_user(username='prot', is_protected=True)
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(f'/api/auth/users/{protected_user.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert User.objects.filter(username='prot').exists()
