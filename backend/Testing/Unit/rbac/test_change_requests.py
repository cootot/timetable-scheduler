import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from core.models import ChangeRequest

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    return User.objects.create_user(username='admin', role='ADMIN')

@pytest.fixture
def hod_user(db):
    return User.objects.create_user(username='hod', role='HOD', department='CSE')

@pytest.fixture
def hod_user_2(db):
    return User.objects.create_user(username='hod2', role='HOD', department='ECE')

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestChangeRequestRBAC:
    """Tests for role-based viewing and approval of change requests"""

    def test_hod_sees_only_own_requests(self, api_client, hod_user, hod_user_2):
        # Create request for HOD 1
        ChangeRequest.objects.create(requested_by=hod_user, target_model='Teacher', change_type='CREATE', proposed_data={})
        # Create request for HOD 2
        ChangeRequest.objects.create(requested_by=hod_user_2, target_model='Teacher', change_type='CREATE', proposed_data={})
        
        api_client.force_authenticate(user=hod_user)
        response = api_client.get('/api/change-requests/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 1
        assert response.data['results'][0]['requested_by'] == hod_user.id

    def test_admin_sees_all_requests(self, api_client, admin_user, hod_user, hod_user_2):
        ChangeRequest.objects.create(requested_by=hod_user, target_model='Teacher', change_type='CREATE', proposed_data={})
        ChangeRequest.objects.create(requested_by=hod_user_2, target_model='Teacher', change_type='CREATE', proposed_data={})
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.get('/api/change-requests/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2

    def test_approval_restricted_to_admin(self, api_client, hod_user):
        req = ChangeRequest.objects.create(requested_by=hod_user, target_model='Teacher', change_type='CREATE', proposed_data={})
        api_client.force_authenticate(user=hod_user)
        response = api_client.post(f'/api/change-requests/{req.id}/approve/')
        assert response.status_code == status.HTTP_403_FORBIDDEN
