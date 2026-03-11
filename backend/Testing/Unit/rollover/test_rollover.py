import pytest
from django.urls import reverse
from core.models import (
    Teacher, Course, Section, TeacherCourseMapping, 
    Schedule, ScheduleEntry, AuditLog
)

from unittest.mock import patch

@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestSemesterRollover:
    def test_rollover_safety_lock(self, api_client, admin_user):
        """Test that missing confirmation fails."""
        api_client.force_authenticate(user=admin_user)
        url = reverse('reset-semester')
        
        # 1. No confirmation
        response = api_client.post(url, {})
        assert response.status_code == 400
        assert "Safety lock active" in response.data['error']
        
        # 2. Wrong confirmation
        response = api_client.post(url, {'confirmation': 'YES'})
        assert response.status_code == 400

    @patch('core.system_views._create_db_backup')
    def test_rollover_success(self, mock_backup, api_client, admin_user, sample_data):
        """Test full rollover process with mocked backup."""
        # Setup mock
        mock_backup.return_value = {
            'filename': 'db_backup_mock.sqlite3',
            'size_display': '10 MB',
            'message': 'Backup created'
        }
        
        api_client.force_authenticate(user=admin_user)
        url = reverse('reset-semester')
        
        # Setup initial state
        teacher = sample_data['teacher']
        course = sample_data['course']
        section = sample_data['section']
        
        # Create mapping (Should be deleted)
        TeacherCourseMapping.objects.create(teacher=teacher, course=course)
        
        # Create Schedule (Should be deleted)
        schedule = Schedule.objects.create(name="Sem 1", semester='odd', year=1)
        
        # Verify initial state
        assert TeacherCourseMapping.objects.count() == 1
        assert Schedule.objects.count() == 1
        assert Section.objects.count() == 1
        
        # Execute Rollover
        response = api_client.post(url, {'confirmation': 'CONFIRM'})
        
        # Debug output if failed
        if response.status_code != 200:
            print(response.data)
            
        assert response.status_code == 200
        assert "Semester reset successful" in response.data['message']
        
        # Verify Backup was called
        mock_backup.assert_called_once()
        
        # Verify Deletions
        assert Schedule.objects.count() == 0
        assert TeacherCourseMapping.objects.count() == 0
        
        # Verify Preservation
        assert Section.objects.filter(class_id=section.class_id).exists()
        assert Teacher.objects.filter(teacher_id=teacher.teacher_id).exists()
        assert Course.objects.filter(course_id=course.course_id).exists()
        
        # Verify Audit Log
        assert AuditLog.objects.filter(action='UPDATE', object_id='SEMESTER_RESET').exists()
