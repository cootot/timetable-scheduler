import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from core.models import Constraint

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username='admin', role='ADMIN')

@pytest.fixture
def hod_user(db):
    return User.objects.create_user(username='hod', role='HOD')

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestGovernanceRBAC:
    """Tests for system governance access (Audit Logs, Constraints)"""

    def test_audit_logs_denied_faculty(self, api_client):
        faculty = User.objects.create_user(username='fac', role='FACULTY')
        api_client.force_authenticate(user=faculty)
        response = api_client.get('/api/audit-logs/')
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_audit_logs_accessible_hod(self, api_client, hod_user):
        api_client.force_authenticate(user=hod_user)
        response = api_client.get('/api/audit-logs/')
        assert response.status_code == status.HTTP_200_OK

    def test_constraints_write_restricted_to_admin(self, api_client, hod_user):
        api_client.force_authenticate(user=hod_user)
        data = {"name": "Test Constraint", "constraint_type": "HARD", "description": "Test", "weight": 5}
        response = api_client.post('/api/constraints/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_constraints_write_allowed_admin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        data = {"name": "Admin Constraint", "constraint_type": "HARD", "description": "Test", "weight": 10}
        response = api_client.post('/api/constraints/', data)
        assert response.status_code == status.HTTP_201_CREATED
