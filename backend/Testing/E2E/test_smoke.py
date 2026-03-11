import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
class TestE2ESmoke:
    def setup_method(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username='admin_e2e',
            email='admin@e2e.com',
            password='password123',
            role='ADMIN'
        )
        self.client.force_authenticate(user=self.admin_user)

    def test_dashboard_access_e2e(self):
        """Verify that an admin can access the dashboard and core endpoints."""
        # This simulates a high-level E2E flow
        response = self.client.get('/api/accounts/user-profile/')
        assert response.status_code == 200
        assert response.data['username'] == 'admin_e2e'

    def test_schedule_list_access_e2e(self):
        """Verify that the schedule list endpoint is accessible."""
        response = self.client.get('/api/scheduler/timetables/')
        assert response.status_code == 200
