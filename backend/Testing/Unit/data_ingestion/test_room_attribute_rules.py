"""
Module 2: Institutional Modeling & Data Ingestion
Unit Test: Room Attribute Rules
Tests performed:
- TC_ROOM_01: Lab course in Lab room (Allowed)
- TC_ROOM_02: Lab course in Lecture room (Blocked)
"""

def check_room_attributes(course_type, room_type):
    """
    Enforces rules for room assignment based on course type.
    Rule: LAB courses must occur in LAB rooms.
    """
    # Check if a Lab course is being assigned to a non-Lab room
    if course_type == "LAB" and room_type != "LAB":
        raise ValueError("Lab course cannot be assigned to lecture room")
    return True

def test_lab_in_lab_room():
    """Test Case TC_ROOM_01: Verify that assigning a Lab course to a Lab room is allowed."""
    assert check_room_attributes("LAB", "LAB") is True

def test_lab_in_lecture_room():
    """Test Case TC_ROOM_02: Verify that assigning a Lab course to a Lecture room is blocked."""
    # We expect a ValueError here
    try:
        check_room_attributes("LAB", "LECTURE")
        # If no error is raised, the test should fail
        assert False, "Should have raised ValueError"
    except ValueError:
        # If error is raised as expected, the test passes
        assert True
