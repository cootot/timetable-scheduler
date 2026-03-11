"""
Unit Tests for Constraint Validation

Tests the scheduling constraint validation system.

Author: Test Team (Kanishthika)
Sprint: 1
"""

import pytest
from datetime import time
from core.models import (
    Teacher, Course, Room, TimeSlot, Section, Schedule, ScheduleEntry
)
from scheduler.constraints import ConstraintValidator


@pytest.mark.django_db(databases=['default', 'audit_db'])
class TestConstraintValidator:
    """Test cases for constraint validation"""
    
    @pytest.fixture
    def setup_data(self):
        """Set up test data"""
        # Create schedule
        schedule = Schedule.objects.create(
            name='Test Schedule',
            semester='odd',
            year=1,
            status='GENERATING'
        )
        
        # Create teacher
        teacher = Teacher.objects.create(
            teacher_id='T001',
            teacher_name='Dr. Test',
            email='test@example.com',
            department='CSE',
            max_hours_per_week=18
        )
        
        # Create course
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
        
        # Create room
        room = Room.objects.create(
            room_id='A-101',
            block='A',
            floor=1,
            room_type='CLASSROOM'
        )
        
        # Create timeslot
        timeslot = TimeSlot.objects.create(
            slot_id='MON-1',
            day='MON',
            slot_number=1,
            start_time=time(9, 0),
            end_time=time(10, 0)
        )
        
        # Create section
        section = Section.objects.create(
            class_id='CSE1A',
            year=1,
            section='A',
            department='CSE'
        )
        
        return {
            'schedule': schedule,
            'teacher': teacher,
            'course': course,
            'room': room,
            'timeslot': timeslot,
            'section': section
        }
    
    def test_faculty_availability_valid(self, setup_data):
        """Test faculty availability when slot is free"""
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, error = validator.validate_faculty_availability(
            setup_data['teacher'],
            setup_data['timeslot']
        )
        assert is_valid is True
        assert error is None
    
    def test_faculty_availability_conflict(self, setup_data):
        """Test faculty availability when already scheduled"""
        # Create an existing entry
        ScheduleEntry.objects.create(
            schedule=setup_data['schedule'],
            section=setup_data['section'],
            course=setup_data['course'],
            teacher=setup_data['teacher'],
            room=setup_data['room'],
            timeslot=setup_data['timeslot'],
            is_lab_session=False
        )
        
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, error = validator.validate_faculty_availability(
            setup_data['teacher'],
            setup_data['timeslot']
        )
        assert is_valid is False
        assert 'already scheduled' in error.lower()
    
    def test_room_availability_valid(self, setup_data):
        """Test room availability when room is free"""
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, error = validator.validate_room_availability(
            setup_data['room'],
            setup_data['timeslot']
        )
        assert is_valid is True
        assert error is None
    
    def test_room_type_match_valid(self, setup_data):
        """Test room type matching for theory course"""
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, error = validator.validate_room_type_match(
            setup_data['course'],
            setup_data['room']
        )
        assert is_valid is True
    
    def test_room_type_match_invalid(self, setup_data):
        """Test room type matching for lab session in classroom"""
        # Create lab course
        lab_course = Course.objects.create(
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
        
        validator = ConstraintValidator(setup_data['schedule'])
        # Lab SESSION in a CLASSROOM should be invalid
        is_valid, error = validator.validate_room_type_match(
            lab_course,
            setup_data['room'],
            is_lab_session=True
        )
        assert is_valid is False
        assert 'LAB' in error
    
    def test_section_availability_valid(self, setup_data):
        """Test section availability when section is free"""
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, error = validator.validate_section_availability(
            setup_data['section'],
            setup_data['timeslot']
        )
        assert is_valid is True
        assert error is None
    
    def test_validate_all_success(self, setup_data):
        """Test all validations passing"""
        validator = ConstraintValidator(setup_data['schedule'])
        is_valid, errors = validator.validate_all(
            setup_data['section'],
            setup_data['course'],
            setup_data['teacher'],
            setup_data['room'],
            setup_data['timeslot']
        )
        assert is_valid is True
        assert len(errors) == 0
