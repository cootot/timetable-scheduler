import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from core.models import User, Teacher, ChangeRequest, Course, TeacherCourseMapping

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def setup_users_and_data(db):
    # Create Admin
    admin = User.objects.create_user(
        username='admin', 
        password='password123', 
        email='admin@university.edu', 
        role='ADMIN'
    )
    
    # Create HOD
    hod = User.objects.create_user(
        username='hod_cse', 
        password='password123', 
        email='hod_cse@university.edu', 
        role='HOD', 
        department='CSE'
    )
    
    # Create Teacher
    teacher = Teacher.objects.create(
        teacher_id='T_TEST_1',
        teacher_name='Test Faculty',
        department='CSE',
        email='faculty@university.edu',
        max_hours_per_week=16
    )
    
    # Create Course
    course = Course.objects.create(
        course_id='CSE101',
        course_name='Intro to Programming',
        year=1,
        semester=1,
        credits=3,
        lectures=3,
        theory=3,
        practicals=0,
        weekly_slots=3
    )

    return {
        'admin': admin,
        'hod': hod,
        'teacher': teacher,
        'course': course
    }

@pytest.mark.django_db(databases=['default', 'audit_db'])
def test_hod_admin_change_request_workflow(api_client, setup_users_and_data):
    """
    Tests the End-to-End integration of generating a change request as an HOD
    and approving it as an Admin.
    """
    data = setup_users_and_data
    hod = data['hod']
    admin = data['admin']
    teacher = data['teacher']
    course = data['course']
    
    # Authenticate as HOD
    api_client.force_authenticate(user=hod)
    
    # 1. HOD Creates a Change Request to add a mapping
    request_data = {
        'target_model': 'Teacher',
        'change_type': 'CREATE',
        'proposed_data': {
            'teacher_id': 'T_TEST_2',
            'teacher_name': 'New Faculty',
            'department': 'CSE',
            'email': 'new_faculty@university.edu',
            'max_hours_per_week': 16
        },
        'request_notes': 'Requested by HOD for the new semester.'
    }
    
    url = '/api/change-requests/'
    response = api_client.post(url, request_data, format='json')
    
    if response.status_code != 201:
        print("REQUEST FAILED:", response.data)
        
    assert response.status_code == status.HTTP_201_CREATED
    request_id = response.data['id']
    
    # Verify HOD Dashboard metric endpoint sees it
    pending_url = '/api/change-requests/pending_count/'
    pending_response = api_client.get(pending_url)
    assert pending_response.data['count'] == 1
    
    # 2. HOD cannot approve their own request (Admin only)
    approve_url = f'/api/change-requests/{request_id}/approve/'
    fail_response = api_client.post(approve_url)
    assert fail_response.status_code == status.HTTP_403_FORBIDDEN
    
    # 3. Authenticate as Admin
    api_client.force_authenticate(user=admin)
    
    # 4. Admin Approves the Request
    approve_data = {'admin_notes': 'Looks good, schedule is clear.'}
    success_response = api_client.post(approve_url, approve_data, format='json')
    
    assert success_response.status_code == status.HTTP_200_OK
    assert success_response.data['status'] == 'APPROVED'
    
    # 5. Verify the actual mapping was created in the database behind the scenes
    mapping_exists = Teacher.objects.filter(
        teacher_id='T_TEST_2'
    ).exists()
    
    assert mapping_exists is True

    # 6. Verify Dashboard Pending count is back to 0
    api_client.force_authenticate(user=hod)
    final_pending_response = api_client.get(pending_url)
    assert final_pending_response.data['count'] == 0
