import pytest
from django.urls import reverse
from rest_framework import status
from core.models import Schedule

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestSchedulerAPI:
    
    def test_get_timetable_unauthorized(self, api_client):
        """
        Ensure unauthenticated requests to timetable endpoint return 401.
        """
        url = reverse('timetable-view')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_timetable_authorized(self, api_client, faculty_user, generated_schedule):
        """
        Ensure authenticated users can access the timetable view.
        """
        api_client.force_authenticate(user=faculty_user)
        url = reverse('timetable-view')
        # We need to pass a schedule_id or the view returns 400
        response = api_client.get(url, {'schedule_id': generated_schedule.schedule_id})
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, dict)

    def test_generate_schedule_unauthorized(self, api_client, faculty_user):
        """
        Ensure non-admin users cannot trigger schedule generation.
        """
        api_client.force_authenticate(user=faculty_user)
        url = reverse('generate-schedule')
        payload = {
            'name': 'Test Schedule',
            'semester': 'odd',
            'year': 1
        }
        response = api_client.post(url, payload)
        # Should be 403 Forbidden because of IsHODOrAdmin permission
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_generate_schedule_authorized(self, api_client, admin_user, sample_data):
        """
        Ensure admin users can trigger schedule generation with valid payload.
        """
        api_client.force_authenticate(user=admin_user)
        url = reverse('generate-schedule')
        payload = {
            'name': 'New Schedule',
            'semester': 'odd',
            'year': 1
        }
        response = api_client.post(url, payload)
        
        # The view returns 202 ACCEPTED as it's an asynchronous task
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert Schedule.objects.filter(name='New Schedule').exists()
        assert response.data['status'] in ['PENDING', 'GENERATING', 'COMPLETED']

    def test_generate_schedule_invalid_payload(self, api_client, admin_user):
        """
        Ensure invalid payload returns 400 Bad Request.
        """
        api_client.force_authenticate(user=admin_user)
        url = reverse('generate-schedule')
        # Missing semester and year
        payload = {
            'name': 'Incomplete Schedule'
        }
        response = api_client.post(url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
