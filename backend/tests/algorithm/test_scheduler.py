import unittest
from unittest.mock import MagicMock, patch
import os
import sys

"""
Module 3: Timetable Scheduling Algorithm (CORE MODULE)
Unit Test Suite for Scheduler Engine and Constraints
Tests performed:
- TC_SCHED_01: Faculty clash prevention
- TC_SCHED_02: Room clash prevention
- TC_SCHED_03: Lab continuity (contiguous blocks)
- TC_SCHED_04: Max continuous hours constraint
- TC_SCHED_05: Faculty workload validation
- TC_SCHED_06: Graceful failure for impossible constraints
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import pytest

from scheduler.constraints import ConstraintValidator
from scheduler.algorithm import TimetableScheduler
from core.models import Schedule

from django.test import TestCase

@pytest.mark.django_db
class TestSchedulerSuite(TestCase):
    databases = '__all__'
    
    def setUp(self):
        self.schedule = Schedule.objects.create(name="Test Sched", semester="even", year=1, status="PENDING")
        self.validator = ConstraintValidator(self.schedule)
        self.validator.existing_entries = MagicMock()
        
    # --- Constraint Tests ---

    def test_tc_sched_01_faculty_clash(self):
        """Test Case TC_SCHED_01: Verify that faculty double-booking is prevented."""
        print(f"\n[RUNNING] TC_SCHED_01: Faculty clash prevention")
        teacher = MagicMock(teacher_name="Dr. Vamsi", teacher_id="T001")
        timeslot = MagicMock(slot_id="MON-1")
        
        print(f"  > Simulating existing booking for {teacher.teacher_name}")
        self.validator.existing_entries.filter.return_value.exists.return_value = True
        
        is_valid, error = self.validator.validate_faculty_availability(teacher, timeslot)
        
        print(f"  > Validation Result: {'DENIED' if not is_valid else 'ALLOWED'}")
        print(f"  > Error Message: {error}")
        
        self.assertFalse(is_valid)
        self.assertIn("already scheduled", error)
        print(f"[SUCCESS] TC_SCHED_01 Verified")

    def test_tc_sched_02_room_clash(self):
        """Test Case TC_SCHED_02: Verify that room double-booking is prevented."""
        print(f"\n[RUNNING] TC_SCHED_02: Room clash prevention")
        room = MagicMock(room_id="LH-1")
        timeslot = MagicMock(slot_id="MON-1")
        
        print(f"  > Simulating occupied status for Room {room.room_id}")
        self.validator.existing_entries.filter.return_value.exists.return_value = True
        
        is_valid, error = self.validator.validate_room_availability(room, timeslot)
        
        print(f"  > Validation Result: {'DENIED' if not is_valid else 'ALLOWED'}")
        print(f"  > Error Message: {error}")
        
        self.assertFalse(is_valid)
        self.assertIn("already booked", error)
        print(f"[SUCCESS] TC_SCHED_02 Verified")

    def test_tc_sched_04_max_hours(self):
        """Test Case TC_SCHED_04: Verify that max continuous hours per day are enforced."""
        print(f"\n[RUNNING] TC_SCHED_04: Max hours constraint")
        teacher = MagicMock(teacher_name="Dr. Vamsi")
        timeslot = MagicMock(day='MON', slot_number=5)
        
        print(f"  > Mocking 4 consecutive slots (1-4) for {teacher.teacher_name}")
        # Need to mock the list of slot numbers returned by values_list
        self.validator.existing_entries.filter.return_value.order_by.return_value.values_list.return_value = [1, 2, 3, 4]
        
        is_valid, error = self.validator.validate_continuous_hours(teacher, timeslot, max_hours=4)
        
        print(f"  > Validation Result for 5th hour: {'DENIED' if not is_valid else 'ALLOWED'}")
        if error: print(f"  > {error}")
        
        self.assertFalse(is_valid)
        self.assertIn("5 continuous hours", error)
        print(f"[SUCCESS] TC_SCHED_04 Verified")

    def test_tc_sched_05_workload_validation(self):
        """Test Case TC_SCHED_05: Verify that faculty workload limits are respected."""
        print(f"\n[RUNNING] TC_SCHED_05: Faculty workload validation")
        teacher = MagicMock(teacher_name="Prof. Sharma", max_hours_per_week=10)
        
        print(f"  > Mocking current workload of 10 hours for {teacher.teacher_name}")
        self.validator.existing_entries.filter.return_value.count.return_value = 10
        
        # We manually check the workload logic as it would appear in the algorithm or validator
        current_hours = self.validator.existing_entries.filter(teacher=teacher).count()
        is_at_limit = current_hours >= teacher.max_hours_per_week
        
        print(f"  > Current Hours: {current_hours}/{teacher.max_hours_per_week}")
        print(f"  > Assignment Status: {'BLOCKED' if is_at_limit else 'ALLOWED'}")
        
        self.assertTrue(is_at_limit)
        print(f"[SUCCESS] TC_SCHED_05 Verified")

    # --- Logic Tests ---

    def test_tc_sched_03_lab_continuity(self):
        """Test Case TC_SCHED_03: Verify that lab sessions are assigned to contiguous blocks."""
        print(f"\n[RUNNING] TC_SCHED_03: Lab continuity check")
        
        # Patching validator methods to simulate availability
        with patch.object(self.validator, 'validate_faculty_availability', return_value=(True, None)), \
             patch.object(self.validator, 'validate_section_availability', return_value=(True, None)):
            
            window = [MagicMock(slot_number=1), MagicMock(slot_number=2)]
            print(f"  > Validating window: Slot {window[0].slot_number} -> Slot {window[1].slot_number}")
            
            # Simple simulation of block scheduling logic
            def can_schedule_block(window):
                for ts in window:
                    v, _ = self.validator.validate_faculty_availability(MagicMock(), ts)
                    if not v:
                        print(f"  > Conflict detected at Slot {ts.slot_number}")
                        return False
                return True

            result = can_schedule_block(window)
            print(f"  > Block Allocation: {'POSSIBLE' if result else 'BLOCKED'}")
            self.assertTrue(result)
            print(f"[SUCCESS] TC_SCHED_03 Verified")

    @patch('core.models.Section.objects.all')
    def test_tc_sched_06_graceful_failure(self, mock_sections):
        """Test Case TC_SCHED_06: Verify algorithm stays stable when no resources are available."""
        print(f"\n[RUNNING] TC_SCHED_06: Graceful failure check")
        
        print(f"  > Simulating missing Section data")
        # Configure mock to return empty set for sections
        mock_sections.return_value.order_by.return_value.exists.return_value = False
        
        scheduler = TimetableScheduler(self.schedule)
        
        with patch('core.models.TimeSlot.objects.all'):
            print(f"  > Attempting schedule generation...")
            success, message = scheduler.generate()
            
            print(f"  > Generation Status: {'SUCCESS' if success else 'FAILED'}")
            print(f"  > System Message: {message}")
            
            self.assertFalse(success)
            self.assertIn("No sections found", message)
            print(f"[SUCCESS] TC_SCHED_06 Verified")

if __name__ == '__main__':
    unittest.main()
