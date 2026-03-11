import pytest

"""
Module 2: Institutional Modeling & Data Ingestion
Unit Test: Student Section Mapping
Tests performed:
- TC_SEC_01: Valid section-course mapping
- TC_SEC_02: Duplicate mapping detection
"""

# Mock data for existing sections
existing_sections = ["CSE-A", "CSE-B"]

# Mock storage for mappings to detect duplicates
section_course_map = {}

def map_course_to_section(section, course):
    """
    Validates and creates a mapping between a section and a course.
    Checks:
    1. Section existence
    2. Duplicate mapping prevention
    """
    # 1. Check if section exists
    if section not in existing_sections:
        raise ValueError(f"Invalid section: {section}")
    
    # 2. Check for duplicate mapping
    if (section, course) in section_course_map:
        raise ValueError(f"Duplicate mapping: {section} is already mapped to {course}")
    
    # Store the mapping
    section_course_map[(section, course)] = True
    return True

def test_valid_section_mapping():
    """Test Case TC_SEC_01: Verify that a valid section-course mapping is accepted."""
    # Ensure fresh state for this test if needed, or use different data
    assert map_course_to_section("CSE-A", "CS101") is True

def test_duplicate_section_mapping():
    """Test Case TC_SEC_02: Verify that duplicate mappings are rejected."""
    # Create initial mapping
    map_course_to_section("CSE-B", "CS102")
    
    # Try to map the same section and course again
    try:
        map_course_to_section("CSE-B", "CS102")
        # Should fail if no error raised
        assert False, "Should have raised ValueError for duplicate mapping"
    except ValueError:
        # Expected behavior
        assert True
