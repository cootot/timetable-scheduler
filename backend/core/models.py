"""
Core Data Models for M3 Timetable Scheduling System
===================================================

This module defines all the core data models representing the domain of the 
timetable scheduling system. These models map directly to database tables 
using Django's ORM (Object-Relational Mapping).

Models included in this file:
- User: Extended user account model with RBAC (Role-Based Access Control)
- AuditLog: For tracking critical system changes
- ChangeRequest: For managing HOD requests to change data
- Teacher: Represents a faculty member
- Course: Represents an academic course
- Room: Represents a physical room or lab
- WalkingTime: Represents transit time between academic blocks
- TimeSlot: Represents a specific period in the week
- Section: Represents a group of students (e.g., CSE-3A)
- TeacherCourseMapping: Many-to-many relationship defining who can teach what
- Schedule, ScheduleEntry: Generated timetables and their specific class placements
- Constraint, ConflictLog: Scheduling rules and rule-violations
- Notification: In-app alerts for users

Author: Backend Team (Vamsi, Akshitha)
Sprint: 1
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Extended user model with roles and department for RBAC.
    Inherits from Django's AbstractUser to provide standard authentication fields
    (username, password, email, first_name, last_name).
    """
    # Define available roles for users in the system
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),          # Full system access
        ('HOD', 'Head of Department'),       # Department-level access
        ('FACULTY', 'Faculty Member'),       # Read-only or limited access
    ]
    
    # User's assigned role, defaulting to FACULTY
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='FACULTY')
    # Custom unique identifier for the user (e.g., employee ID)
    user_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    # The department this user belongs to (e.g., 'CSE', 'ECE')
    department = models.CharField(max_length=50, blank=True)
    # Contact phone number for the user
    phone = models.CharField(max_length=15, blank=True)
    # Flag to prevent accidental deletion of critical core accounts (like superadmin)
    is_protected = models.BooleanField(default=False)
    
    # Link the user account directly to a Teacher entity for faculty/HODs
    # Setting null=True allows Admin users to exist without a Teacher record
    teacher = models.ForeignKey(
        'Teacher',
        on_delete=models.SET_NULL,           # If Teacher gets deleted, keep the User account but set this field to null
        null=True,
        blank=True,
        related_name='user_account',         # Allows reverse lookup (Teacher.user_account)
        help_text="Linked teacher record for faculty/HOD users"
    )
    
    class Meta:
        db_table = 'users'                   # Custom database table name


class AuditLog(models.Model):
    """
    Track critical system changes for accountability.
    Stored in a separate database (audit_db) configured via database routers
    to survive normal backup/restore operations.
    """
    # Define the types of actions being logged
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('LOGIN', 'Logged In'),
        ('LOGOUT', 'Logged Out'),
        ('GENERATE', 'Generated Schedule'),
        ('BACKUP', 'Backup Created'),
        ('RESTORE', 'Database Restored'),
    ]
    
    # The name of the user who performed the action (stored as string to prevent dangling foreign keys if user is deleted)
    user_name = models.CharField(max_length=150, blank=True, null=True)
    # The action that was performed
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    # The name of the Django model that was affected (e.g., 'Teacher', 'Schedule')
    model_name = models.CharField(max_length=50)
    # The primary key ID of the affected object
    object_id = models.CharField(max_length=100, blank=True, null=True)
    # JSON dictionary storing specific details about the change (e.g., {"old_name": "A", "new_name": "B"})
    details = models.JSONField(default=dict)
    # The IP address from which the action was initiated
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    # The exact timestamp when the action occurred (auto-populated on creation)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'              # Custom table name
        ordering = ['-timestamp']             # Default ordering: newest logs first


class ChangeRequest(models.Model):
    """
    Track modification requests from HODs that require Admin approval.
    
    Workflow:
    1. HOD submits a change (status: PENDING)
    2. Admin reviews the proposed_data vs current_data
    3. Admin approves (status: APPROVED, applies change) or rejects (status: REJECTED)
    """
    # State of the change request
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    # What kind of database operation the HOD is requesting
    CHANGE_TYPE_CHOICES = [
        ('CREATE', 'Create New'),
        ('UPDATE', 'Update Existing'),
        ('DELETE', 'Delete'),
        ('SWAP', 'Swap Faculty'),
    ]
    
    # The HOD user who submitted the request
    requested_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,            # Delete request if HOD user is deleted
        related_name='change_requests',
        help_text="HOD who submitted this request"
    )
    # Which model the change applies to (e.g., 'Teacher', 'Course')
    target_model = models.CharField(
        max_length=50,
        help_text="Model being modified (e.g., 'Teacher')"
    )
    # Which specific row is being modified (None if creating a new row)
    target_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="ID of the object being modified (null for CREATE)"
    )
    # Type of change desired
    change_type = models.CharField(
        max_length=20, 
        choices=CHANGE_TYPE_CHOICES,
        help_text="Type of change requested"
    )
    # The new data the HOD wants to insert/update (stored flexibly as JSON)
    proposed_data = models.JSONField(
        help_text="New or modified data in JSON format"
    )
    # A snapshot of the data before the change (for diffing/reverting)
    current_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Current data before change (for UPDATE/DELETE)"
    )
    # Workflow status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )
    # HOD's rationale for needing this change
    request_notes = models.TextField(
        blank=True,
        help_text="HOD's explanation for the change"
    )
    # Admin's rationale for approving or rejecting
    admin_notes = models.TextField(
        blank=True,
        help_text="Admin's notes when reviewing"
    )
    # When the request was made
    created_at = models.DateTimeField(auto_now_add=True)
    # When the admin processed it
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # The Admin user who reviewed it
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='reviewed_requests',
        help_text="Admin who approved/rejected this request"
    )
    
    class Meta:
        db_table = 'change_requests'
        ordering = ['-created_at']           # Newest requests first
    
    def __str__(self):
        # String representation for the Django admin panel
        return f"{self.change_type} {self.target_model} by {self.requested_by.username} - {self.status}"


class Teacher(models.Model):
    """
    Represents a faculty member who teaches courses.
    This is independent of the User model, though a User can link to a Teacher.
    """
    # Primary Key - Unique teacher ID (e.g., T001)
    teacher_id = models.CharField(max_length=10, unique=True, primary_key=True)
    # Full name of the faculty member
    teacher_name = models.CharField(max_length=100)
    # Institutional email address
    email = models.EmailField()
    # Department the teacher belongs to (e.g., CSE)
    department = models.CharField(max_length=50)
    # Maximum number of hours this teacher is allowed to teach in one week (used by algorithm)
    max_hours_per_week = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(40)]
    )
    
    class Meta:
        db_table = 'teachers'
        ordering = ['teacher_id']            # Alphabetical by ID
    
    def __str__(self):
        return f"{self.teacher_id} - {self.teacher_name}"


class Course(models.Model):
    """
    Represents an academic course (subject) offered by the institution.
    """
    # Primary Key - Unique course code (e.g., CS101)
    course_id = models.CharField(max_length=20, unique=True, primary_key=True)
    # Official title of the course
    course_name = models.CharField(max_length=200)
    # Academic year this course belongs to (1st, 2nd, 3rd, 4th)
    year = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    # Semester type (ODD semesters like 1,3,5,7 or EVEN semesters like 2,4,6,8)
    semester = models.CharField(max_length=10, choices=[('odd', 'Odd'), ('even', 'Even')])
    # Number of lecture hours required per week
    lectures = models.IntegerField(validators=[MinValueValidator(0)])
    # Number of theory hours required per week
    theory = models.IntegerField(validators=[MinValueValidator(0)])
    # Number of practical/lab hours required per week
    practicals = models.IntegerField(validators=[MinValueValidator(0)])
    # Academic weight of this course
    credits = models.IntegerField(validators=[MinValueValidator(0)])
    # Flag indicating if this course occurs entirely in a lab setting
    is_lab = models.BooleanField(default=False)
    # Flag indicating if this is an elective (students choose it) vs a core course
    is_elective = models.BooleanField(default=False)
    # Categorization of electric type (e.g., "Professional Elective I")
    elective_type = models.CharField(max_length=100, null=True, blank=True)
    # The grouping logic for electives (e.g., PE_SEM5, FREE_SEM4) to schedule them together
    elective_group = models.CharField(max_length=50, null=True, blank=True)
    # Flag to determine if this course should be actively scheduled (vs AVP/CIR courses that might not be)
    is_schedulable = models.BooleanField(default=True)
    # Flag indicating if this is a project-based course
    is_project = models.BooleanField(default=False)
    # Flag indicating if this is an ADM (Administrative) course
    is_adm = models.BooleanField(default=False)
    # Total weekly slots required for this course (usually lectures + theory + practicals)
    weekly_slots = models.IntegerField(validators=[MinValueValidator(0)])
    
    class Meta:
        db_table = 'courses'
        ordering = ['year', 'semester', 'course_id']
    
    def __str__(self):
        return f"{self.course_id} - {self.course_name}"


class Room(models.Model):
    """
    Represents a physical room/classroom or laboratory in the institution.
    """
    # Allowed room classifications
    ROOM_TYPES = [
        ('CLASSROOM', 'Classroom'),
        ('LAB', 'Laboratory'),
    ]
    
    # Primary Key - Unique room number (e.g., A-101)
    room_id = models.CharField(max_length=20, unique=True, primary_key=True)
    # The building block this room is located in (Used for calculating walking times)
    block = models.CharField(max_length=10)
    # Floor number (1, 2, 3...)
    floor = models.IntegerField(validators=[MinValueValidator(1)])
    # Indicates whether it's a standard classroom or a lab
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    # Number of students the room can seat
    capacity = models.IntegerField(default=60, null=True, blank=True, validators=[MinValueValidator(1)])
    
    class Meta:
        db_table = 'rooms'
        ordering = ['block', 'floor', 'room_id']
    
    def __str__(self):
        return f"{self.room_id} ({self.room_type})"


class WalkingTime(models.Model):
    """
    Defines the physical walking time required to travel between two academic blocks.
    Used by the Genetic Algorithm to avoid scheduling a teacher in 'Block A' 
    and then immediately in 'Block B' without sufficient transit time.
    """
    # Starting block
    source_block = models.CharField(max_length=10)
    # Destination block
    target_block = models.CharField(max_length=10)
    # Transit duration in minutes
    minutes = models.IntegerField(validators=[MinValueValidator(0)])
    
    class Meta:
        db_table = "walking_times"
        # Ensure only one record exists per pair of blocks
        unique_together = ["source_block", "target_block"]
        
    def __str__(self):
        return f"{self.source_block} to {self.target_block}: {self.minutes}m"


class TimeSlot(models.Model):
    """
    Represents a discrete predefined time slot in the weekly college schedule.
    """
    # Days of the academic week
    DAYS = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
    ]
    
    # Primary Key - string ID like 'MON_1' or 'M1'
    slot_id = models.CharField(max_length=10, unique=True, primary_key=True)
    # The day this slot occurs on
    day = models.CharField(max_length=3, choices=DAYS)
    # Sequential number of the slot in that day (e.g., 1st period, 2nd period)
    slot_number = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    # Clock start time
    start_time = models.TimeField()
    # Clock end time
    end_time = models.TimeField()
    
    class Meta:
        db_table = 'timeslots'
        ordering = ['day', 'slot_number']
        # Prevent two slot #1s on Monday
        unique_together = ['day', 'slot_number']
    
    def __str__(self):
        return f"{self.day} Slot {self.slot_number} ({self.start_time}-{self.end_time})"


class Section(models.Model):
    """
    Represents a specific class section (group of students traveling together).
    Examples: 'CSE-1A' (Computer Science, 1st Year, Section 'A')
    """
    # Primary Key - Unique identifier (e.g., CSE3A)
    class_id = models.CharField(max_length=20, unique=True, primary_key=True)
    # The academic year of this student cohort (1st, 2nd, 3rd, 4th)
    year = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    # The section division character (e.g., A, B, C)
    section = models.CharField(max_length=5)
    # The department this section belongs to (e.g., 'CSE')
    department = models.CharField(max_length=50)
    
    class Meta:
        db_table = 'sections'
        ordering = ['department', 'year', 'section']
    
    def __str__(self):
        return f"{self.class_id} - Year {self.year} Section {self.section}"


class TeacherCourseMapping(models.Model):
    """
    Maps teachers to the specific courses and sections they are assigned to teach.
    This acts as the blueprint/input for the timetable generation algorithm.
    It indicates "Teacher X needs to teach Course Y to Section Z".
    """
    # The teacher being assigned
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="course_mappings"
    )
    # The course they must teach
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="teacher_mappings"
    )
    # The specific student section they are teaching it to
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, null=True, blank=True, related_name="teacher_mappings"
    )
    # The academic year context
    year = models.IntegerField(null=True, blank=True)
    # Preference level for scheduling constraints (1=Highest priority, 5=Lowest priority)
    preference_level = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=Highest Priority, 5=Lowest Priority (Default=3)",
    )
    # Domain identifier for specialized subject grouping
    domain_id = models.IntegerField(
        null=True, blank=True,
        help_text="Domain number from mappingop/mappingep (e.g. 1=Cyber Security)",
    )
    # The new section_group from elective_allocations indicating which grouped section (A/B/etc) this is
    section_group = models.CharField(max_length=10, null=True, blank=True)
    # Human-readable domain name for electives
    domain_name = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Domain name (e.g. 'Cyber Security', 'Data Science')",
    )

    class Meta:
        db_table = "teacher_course_mapping"
        # Prevent duplicated assignments
        unique_together = ["teacher", "course", "section", "year"]
    
    def __str__(self):
        return f"{self.teacher.teacher_id} -> {self.course.course_id}"


class Schedule(models.Model):
    """
    Represents a complete generated timetable instance containing many ScheduleEntries.
    Allows saving multiple versions/drafts of schedules.
    """
    # Status lifecycle of a schedule generation task
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),          # Queued for AI algorithm
        ('GENERATING', 'Generating'),    # AI algorithm is currently solving it
        ('COMPLETED', 'Completed'),      # AI finished successfully
        ('PUBLISHED', 'Published'),      # Approved and visible to end-users
        ('FAILED', 'Failed'),            # AI hit an error
    ]
    
    # Primary Key
    schedule_id = models.AutoField(primary_key=True)
    # Human readable name (e.g., "Odd Sem 2026 Final")
    name = models.CharField(max_length=200)
    # Versioning number for tracking iterations
    version = models.IntegerField(default=1)
    # Whether this schedule is still being edited manually
    is_draft = models.BooleanField(default=True)
    # Semester context
    semester = models.CharField(
        max_length=10, choices=[("odd", "Odd"), ("even", "Even")]
    )
    # Year context (null for institutional-wide schedules)
    year = models.IntegerField(null=True, blank=True)
    # Current lifecycle state
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    # Creation timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    # Timestamp marked when generation finishes
    completed_at = models.DateTimeField(null=True, blank=True)
    # Fitness/Quality score returned by the Genetic Algorithm (out of 100)
    quality_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    # Frozen JSON copy of the schedule configuration when it was published
    published_snapshot = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Snapshot of the schedule layout when it was published. Used to detect changes even if underlying entries are deleted."
    )
    
    class Meta:
        db_table = 'schedules'
        ordering = ['-created_at']           # Newest schedules first
    
    def __str__(self):
        return f"Schedule {self.schedule_id} - {self.name} ({self.status})"


class ScheduleEntry(models.Model):
    """
    Represents a single "cell" or "block" in the final timetable grid.
    Ties together the Schedule, Section, Course, Teacher, Room, and TimeSlot.
    """
    # Grouping key pointing to the master Schedule
    schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name="entries"
    )
    # Which student section is attending
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    # What subject is being taught
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    # Who is teaching it
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    # Where it is taking place
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    # When it is taking place
    timeslot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    
    # Flag to differentiate theory hours vs practicals (often requires multiple contiguous slots)
    is_lab_session = models.BooleanField(default=False)
    
    # Detailed session type for color coding and refinement
    SESSION_TYPES = [
        ('LECTURE', 'Core Lecture'),
        ('TUTORIAL', 'Core Tutorial'),
        ('PRACTICAL', 'Practical/Lab'),
        ('ADM', 'Administrative'),
        ('PE', 'Professional Elective'),
        ('FE', 'Free Elective'),
    ]
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='LECTURE')
    # AI rationale text explaining why this specific placement occurred
    constraint_reason = models.CharField(
        max_length=300,
        blank=True,
        null=True,
        help_text="Short explanation of why the AI placed this class here (for Explainability Tooltips)",
    )
    # Mutation tracking field to prevent conflicting drag-and-drop manual edits by multiple users
    last_modified = models.DateTimeField(
        auto_now=True,
        help_text="Tracks last modification for optimistic concurrency control",
    )

    class Meta:
        db_table = "schedule_entries"
        # Allow multiple courses in the same slot for parallel electives
        unique_together = [
            ["schedule", "section", "course", "teacher", "timeslot"],
        ]
    
    def __str__(self):
        return f"{self.section.class_id} - {self.course.course_id} @ {self.timeslot.slot_id}"


class Constraint(models.Model):
    """
    A persistent record of the rules the Genetic Algorithm must follow 
    in order to generate a valid and optimal timetable.
    """
    # Category of the rule
    CONSTRAINT_TYPES = [
        ('HARD', 'Hard Constraint'),  # Breaking this makes the timetable completely invalid (e.g., room double booked)
        ('SOFT', 'Soft Constraint'),  # Breaking this is allowed, but lowers quality score (e.g., teacher prefers morning classes)
    ]
    
    # Identifier (e.g., NO_OVERLAPPING_CLASSES)
    name = models.CharField(max_length=100, unique=True)
    # Categorization as HARD or SOFT
    constraint_type = models.CharField(max_length=10, choices=CONSTRAINT_TYPES)
    # Plain text explanation of what the rule does
    description = models.TextField()
    # Number determining how heavily to penalize the genetic algorithm if it breaks this Soft constraint
    weight = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    # Toggle to easily turn rules on or off based on institutional need
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'constraints'
        # Top priority constraints appear first
        ordering = ['-weight', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.constraint_type})"


class ConflictLog(models.Model):
    """
    Logs instances where the AI (or a manual drag-and-drop editor) creates
    a clash or rule violation within a specific Schedule.
    """
    # Severity classification scale
    SEVERITY_LEVELS = [
        ('LOW', 'Low'),              # Very minor soft-constraint break
        ('MEDIUM', 'Medium'),        # Notable soft-constraint break
        ('HIGH', 'High'),            # Severe problem
        ('CRITICAL', 'Critical'),    # Hard constraint broken (impossible real-world scenario)
    ]
    
    # Schedule where the conflict exists
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name='conflicts')
    # Label for what went wrong (e.g., 'TEACHER_DOUBLE_BOOKED')
    conflict_type = models.CharField(max_length=100)
    # Readablity text (e.g., "Dr. Smith assigned to CSE-1A and ECE-2B at MON_1")
    description = models.TextField()
    # The assigned severity rank
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    # When this was detected
    detected_at = models.DateTimeField(auto_now_add=True)
    # Admin toggle to indicate if they've mitigated the issue
    resolved = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'conflict_logs'
        # Show newest and worst conflicts first
        ordering = ['-detected_at', '-severity']
    
    def __str__(self):
        return f"{self.conflict_type} - {self.severity} ({self.schedule.schedule_id})"


class Notification(models.Model):
    """
    System for alerting users (primarily Teachers) when changes occur
    that affect them (like a new published timetable changing their assigned rooms).
    """
    # Destination user
    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text="User who receives this notification"
    )
    # Pointer connecting the notification back to the source Schedule (optional)
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Schedule related to this notification"
    )
    # Headline text shown in the UI bell menu
    title = models.CharField(max_length=200)
    # Deeper descriptive text detailing what exactly changed
    message = models.TextField()
    # Tracking whether the user has dismissed the alert
    is_read = models.BooleanField(default=False)
    # Creation timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        # Newest logs first
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.recipient.username} ({'Read' if self.is_read else 'Unread'})"
