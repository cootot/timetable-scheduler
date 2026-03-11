import pytest

"""
Module 2: Institutional Modeling & Data Ingestion
Unit Test: Referential Integrity
Tests performed:
- TC_REF_01: Valid faculty_id existence check
- TC_REF_02: Invalid faculty_id existence check
"""

# Mock database of existing faculty IDs
existing_faculty_ids = ["F001", "F002"]

def validate_faculty_id(fid):
    """
    Validates if the provided Faculty ID exists in the system.
    This simulates checking against the database (Foreign Key check).
    """
    if fid not in existing_faculty_ids:
        raise ValueError(f"Invalid faculty ID: {fid} does not exist.")
    return True

def test_valid_faculty_id():
    """Test Case TC_REF_01: Verify that an existing faculty ID is accepted."""
    assert validate_faculty_id("F001") is True

def test_invalid_faculty_id():
    """Test Case TC_REF_02: Verify that a non-existent faculty ID is rejected."""
    # Expecting ValueError for unknown ID 'F999'
    with pytest.raises(ValueError):
        validate_faculty_id("F999")
