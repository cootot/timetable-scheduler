import io
import pytest

"""
Module 2: Institutional Modeling & Data Ingestion
Unit Test: CSV Structure Validation
Tests performed:
- TC_CSV_01: Correct CSV headers
- TC_CSV_02: Missing mandatory column
- TC_CSV_04: Empty CSV file
"""

def validate_csv_headers(csv_file):
    """
    Validates that the CSV file has the required headers.
    Required headers: faculty_id, name
    """
    # Read the first line to get headers
    line = csv_file.readline()
    if not line:
        raise ValueError("Empty CSV file")
        
    headers = line.strip().split(",")
    # Define required columns for Faculty CSV
    required = ["faculty_id", "name"]
    
    # Check if all required columns are present
    for col in required:
        if col not in headers:
            raise ValueError(f"Missing required column: {col}")
    return True

def test_valid_csv_headers():
    """Test Case TC_CSV_01: Verify that a CSV with correct headers is accepted.""" 
    # Mocking a valid CSV file content using StringIO
    csv_data = io.StringIO("faculty_id,name\nF001,Dr.A\n")
    assert validate_csv_headers(csv_data) is True

def test_missing_column():
    """Test Case TC_CSV_02: Verify that a CSV missing a required column is rejected."""
    # Mocking CSV content missing 'faculty_id'
    csv_data = io.StringIO("name\nDr.A\n")
    # Expecting a ValueError to be raised
    with pytest.raises(ValueError):
        validate_csv_headers(csv_data)

def test_empty_csv():
    """Test Case TC_CSV_04: Verify that an empty CSV file is rejected."""
    # Mocking an empty CSV file
    csv_data = io.StringIO("")
    # Expecting a ValueError
    with pytest.raises(ValueError):
        validate_csv_headers(csv_data)
