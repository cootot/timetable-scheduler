import pytest
import os
import django
from django.conf import settings
from django.db import models

# Workaround for SQLite JSON support on versions < 3.9.0
class MockJSONField(models.TextField):
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        import json
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    def get_prep_value(self, value):
        if value is None:
            return value
        import json
        return json.dumps(value)

# Patch JSONField
models.JSONField = MockJSONField

# Configure Django settings for pytest
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'timetable_project.settings')

def pytest_configure():
    """Configure Django for pytest"""
    if not settings.configured:
        django.setup()
