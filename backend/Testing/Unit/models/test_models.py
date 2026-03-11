"""
Unit Tests for Core Models

Tests all data models in the M3 Timetable System.

Author: Test Team (Kanishthika)
Sprint: 1
"""

import pytest
from django.core.exceptions import ValidationError
from core.models import (
    Teacher, Course, Room, TimeSlot, Section,
    TeacherCourseMapping, Schedule, ScheduleEntry
)


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestTeacherModel:
    """Test cases for Teacher model"""
    
    def test_create_teacher(self):
        """Test creating a teacher"""
        teacher = Teacher.objects.create(
            teacher_id='T999',
            teacher_name='Test Teacher',
            email='test@example.com',
            department='CSE',
            max_hours_per_week=18
        )
        assert teacher.teacher_id == 'T999'
        assert teacher.teacher_name == 'Test Teacher'
        assert str(teacher) == 'T999 - Test Teacher'
    
    def test_teacher_max_hours_validation(self):
        """Test max hours validation"""
        with pytest.raises(ValidationError):
            teacher = Teacher(
                teacher_id='T998',
                teacher_name='Invalid Teacher',
                email='invalid@example.com',
                department='CSE',
                max_hours_per_week=150  # Exceeds max of 100
            )
            teacher.full_clean()


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestCourseModel:
    """Test cases for Course model"""
    
    def test_create_course(self):
        """Test creating a course"""
        course = Course.objects.create(
            course_id='CS101',
            course_name='Introduction to Programming',
            year=1,
            semester='odd',
            lectures=3,
            theory=3,
            practicals=0,
            credits=3,
            is_lab=False,
            is_elective=False,
            weekly_slots=3
        )
        assert course.course_id == 'CS101'
        assert course.is_lab is False
        assert str(course) == 'CS101 - Introduction to Programming'
    
    def test_lab_course(self):
        """Test creating a lab course"""
        course = Course.objects.create(
            course_id='CS102L',
            course_name='Programming Lab',
            year=1,
            semester='odd',
            lectures=0,
            theory=0,
            practicals=2,
            credits=1,
            is_lab=True,
            is_elective=False,
            weekly_slots=2
        )
        assert course.is_lab is True


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestRoomModel:
    """Test cases for Room model"""
    
    def test_create_classroom(self):
        """Test creating a classroom"""
        room = Room.objects.create(
            room_id='A-101',
            block='A',
            floor=1,
            room_type='CLASSROOM'
        )
        assert room.room_type == 'CLASSROOM'
        assert str(room) == 'A-101 (CLASSROOM)'
    
    def test_create_lab(self):
        """Test creating a lab"""
        room = Room.objects.create(
            room_id='B-201',
            block='B',
            floor=2,
            room_type='LAB'
        )
        assert room.room_type == 'LAB'


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestTimeSlotModel:
    """Test cases for TimeSlot model"""
    
    def test_create_timeslot(self):
        """Test creating a time slot"""
        from datetime import time
        slot = TimeSlot.objects.create(
            slot_id='MON-1',
            day='MON',
            slot_number=1,
            start_time=time(9, 0),
            end_time=time(10, 0)
        )
        assert slot.day == 'MON'
        assert slot.slot_number == 1
        assert 'MON' in str(slot)
        assert 'Slot 1' in str(slot)


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestSectionModel:
    """Test cases for Section model"""
    
    def test_create_section(self):
        """Test creating a section"""
        section = Section.objects.create(
            class_id='CSE1A',
            year=1,
            section='A',
            department='CSE'
        )
        assert section.class_id == 'CSE1A'
        assert section.year == 1
        assert 'CSE1A' in str(section)
        assert 'Year 1' in str(section)


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestScheduleModel:
    """Test cases for Schedule model"""
    
    def test_create_schedule(self):
        """Test creating a schedule"""
        schedule = Schedule.objects.create(
            name='Test Schedule',
            semester='odd',
            year=1,
            status='PENDING'
        )
        assert schedule.name == 'Test Schedule'
        assert schedule.status == 'PENDING'
        # quality_score can be None initially
        assert schedule.quality_score is None or schedule.quality_score == 0.0


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestTeacherCourseMapping:
    """Test cases for TeacherCourseMapping"""
    
    def test_create_mapping(self):
        """Test creating teacher-course mapping"""
        teacher = Teacher.objects.create(
            teacher_id='T001',
            teacher_name='Dr. Smith',
            email='smith@example.com',
            department='CSE',
            max_hours_per_week=18
        )
        course = Course.objects.create(
            course_id='CS101',
            course_name='Programming',
            year=1,
            semester='odd',
            lectures=3,
            theory=3,
            practicals=0,
            credits=3,
            is_lab=False,
            is_elective=False,
            weekly_slots=3
        )
        mapping = TeacherCourseMapping.objects.create(
            teacher=teacher,
            course=course,
            preference_level=5
        )
        assert mapping.teacher == teacher
        assert mapping.course == course
        assert mapping.preference_level == 5
