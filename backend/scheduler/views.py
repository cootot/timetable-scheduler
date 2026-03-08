"""
Scheduler API Views

This module provides API endpoints for schedule generation and analytics.

Author: Backend Team (Vamsi, Akshitha)
Sprint: 1
"""

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg
from core.models import Schedule, ScheduleEntry, Teacher, Room, Section, TimeSlot, Course
from core.serializers import ScheduleSerializer, ScheduleDetailSerializer
from .tasks import generate_schedule_async
from .email_utils import send_publish_notifications, send_deadline_reminders
from accounts.permissions import IsHODOrAdmin, IsFacultyOrAbove


@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def trigger_generation(request):
    """
    Trigger schedule generation.
    """
    name = request.data.get('name', 'Untitled Schedule')
    semester = request.data.get('semester')
    year = request.data.get('year')
    
    if not semester or not year:
        return Response(
            {"error": "semester and year are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create schedule object
    schedule = Schedule.objects.create(
        name=name,
        semester=semester,
        year=year,
        status='PENDING'
    )
    
    # Generate schedule asynchronously (Celery)
    generate_schedule_async.delay(schedule.schedule_id)
    
    serializer = ScheduleSerializer(schedule)
    
    return Response({
        "schedule_id": schedule.schedule_id,
        "status": schedule.status,
        "message": "Schedule generation queued successfully and is processing in the background.",
        "data": serializer.data
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsFacultyOrAbove])
def get_workload_analytics(request):
    """
    Get faculty workload analytics.
    """
    schedule_id = request.query_params.get('schedule_id')
    
    if not schedule_id:
        return Response(
            {"error": "schedule_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get workload data
    workload_data = ScheduleEntry.objects.filter(
        schedule_id=schedule_id
    ).values(
        'teacher__teacher_id',
        'teacher__teacher_name',
        'teacher__max_hours_per_week'
    ).annotate(
        total_hours=Count('id')
    )
    
    # Calculate utilization
    result = []
    for item in workload_data:
        utilization = (item['total_hours'] / item['teacher__max_hours_per_week']) * 100
        result.append({
            'teacher_id': item['teacher__teacher_id'],
            'teacher_name': item['teacher__teacher_name'],
            'total_hours': item['total_hours'],
            'max_hours': item['teacher__max_hours_per_week'],
            'utilization': round(utilization, 2)
        })
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsFacultyOrAbove])
def get_room_utilization(request):
    """
    Get room utilization analytics.
    """
    schedule_id = request.query_params.get('schedule_id')
    
    if not schedule_id:
        return Response(
            {"error": "schedule_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Total available slots (40 timeslots per week)
    total_slots = 40
    
    # Get room utilization data
    room_data = ScheduleEntry.objects.filter(
        schedule_id=schedule_id
    ).values(
        'room__room_id',
        'room__room_type'
    ).annotate(
        total_slots_used=Count('id')
    )
    
    # Calculate utilization
    result = []
    for item in room_data:
        utilization = (item['total_slots_used'] / total_slots) * 100
        result.append({
            'room_id': item['room__room_id'],
            'room_type': item['room__room_type'],
            'total_slots_used': item['total_slots_used'],
            'utilization': round(utilization, 2)
        })
    
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_timetable_view(request):

    """
    Get timetable view for a specific section or teacher.
    
    GET /api/scheduler/timetable?schedule_id=1&section=CSE1A
    GET /api/scheduler/timetable?schedule_id=1&teacher=T001
    
    Returns: Organized timetable data grouped by day and slot
    """
    schedule_id = request.query_params.get('schedule_id')
    section_id = request.query_params.get('section')
    teacher_id = request.query_params.get('teacher')
    
    if not schedule_id:
        return Response(
            {"error": "schedule_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Build query
    query = ScheduleEntry.objects.filter(schedule_id=schedule_id)
    
    if section_id:
        query = query.filter(section_id=section_id)
    if teacher_id:
        query = query.filter(teacher_id=teacher_id)
    
    # Get entries with related data
    entries = query.select_related(
        'section', 'course', 'teacher', 'room', 'timeslot'
    ).order_by('timeslot__day', 'timeslot__slot_number')
    
    # Organize by day and slot
    timetable = {}
    for entry in entries:
        day = entry.timeslot.day
        slot_num = entry.timeslot.slot_number
        
        if day not in timetable:
            timetable[day] = {}
        
        if slot_num not in timetable[day]:
            timetable[day][slot_num] = []
        
        timetable[day][slot_num].append({
            'entry_id': entry.id,
            'course_code': entry.course.course_id,
            'course_name': entry.course.course_name,
            'teacher_id': entry.teacher.teacher_id,
            'teacher_name': entry.teacher.teacher_name,
            'room': entry.room.room_id,
            'section': entry.section.class_id,
            'is_lab_session': entry.is_lab_session,
            'start_time': entry.timeslot.start_time.strftime('%H:%M'),
            'end_time': entry.timeslot.end_time.strftime('%H:%M'),
            'last_modified': entry.last_modified.isoformat(),
        })
    
    return Response(timetable)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_schedule(request):
    """
    Get the schedule for the logged-in faculty member.
    Automatically filters by the linked Teacher record.
    """
    user = request.user
    
    # Check if user is linked to a teacher
    if not hasattr(user, 'teacher') or not user.teacher:
        return Response(
            {"error": "No teacher record linked to this account"},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    teacher_id = user.teacher.teacher_id
    schedule_id = request.query_params.get('schedule_id')
    
    # If no schedule_id provided, get the most recent completed one
    if not schedule_id:
        latest_schedule = Schedule.objects.filter(status='COMPLETED').order_by('-created_at').first()
        if latest_schedule:
            schedule_id = latest_schedule.schedule_id
            
    if not schedule_id:
        return Response(
            {"error": "No generated schedules found"},
            status=status.HTTP_404_NOT_FOUND
        )
        
    # Reuse the logic from get_timetable_view but force teacher_id
    # We can call the internal logic or just reproduce it here
    
    # Query for the specific schedule and teacher
    entries = ScheduleEntry.objects.filter(
        schedule_id=schedule_id,
        teacher_id=teacher_id
    ).select_related(
        'section', 'course', 'teacher', 'room', 'timeslot'
    ).order_by('timeslot__day', 'timeslot__slot_number')
    
    # Organize by day and slot
    timetable = {}
    for entry in entries:
        day = entry.timeslot.day
        slot_num = entry.timeslot.slot_number
        
        if day not in timetable:
            timetable[day] = {}
        
        if slot_num not in timetable[day]:
            timetable[day][slot_num] = []
        
        timetable[day][slot_num].append({
            'course_code': entry.course.course_id,
            'course_name': entry.course.course_name,
            'teacher_name': entry.teacher.teacher_name,
            'room': entry.room.room_id,
            'section': entry.section.class_id,
            'is_lab_session': entry.is_lab_session,
            'start_time': entry.timeslot.start_time.strftime('%H:%M'),
            'end_time': entry.timeslot.end_time.strftime('%H:%M'),
        })
    
    return Response({
        'schedule_id': schedule_id,
        'timetable': timetable
    })


@api_view(['GET'])
@permission_classes([IsHODOrAdmin])
def validate_schedule(request, schedule_id):
    """
    Run hard-constraint integrity checks on a schedule.
    Checks: Teacher double-booking, Room double-booking,
    Section double-booking, Room-type mismatch.
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
    except Schedule.DoesNotExist:
        return Response(
            {"error": "Schedule not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    conflicts = []
    entries = ScheduleEntry.objects.filter(schedule=schedule)

    # 1. Teacher double-booking
    teacher_clashes = (
        entries.values('teacher', 'timeslot')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    for c in teacher_clashes:
        t = Teacher.objects.get(pk=c['teacher'])
        ts = TimeSlot.objects.get(pk=c['timeslot'])
        check_count = c['count']
        conflicts.append(
            f"Teacher '{t.teacher_name}' is assigned {check_count} classes at {ts.day} Slot {ts.slot_number}"
        )

    # 2. Room double-booking
    room_clashes = (
        entries.values('room', 'timeslot')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    for c in room_clashes:
        r = Room.objects.get(pk=c['room'])
        ts = TimeSlot.objects.get(pk=c['timeslot'])
        check_count = c['count']
        conflicts.append(
            f"Room '{r.room_id}' has {check_count} classes at {ts.day} Slot {ts.slot_number}"
        )

    # 3. Section double-booking
    section_clashes = (
        entries.values('section', 'timeslot')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    for c in section_clashes:
        s = Section.objects.get(pk=c['section'])
        ts = TimeSlot.objects.get(pk=c['timeslot'])
        check_count = c['count']
        conflicts.append(
            f"Section '{s.class_id}' has {check_count} classes at {ts.day} Slot {ts.slot_number}"
        )

    # 4. Room-type mismatch (lab session in theory room or vice versa)
    for entry in entries.select_related('course', 'room'):
        room = entry.room
        if entry.is_lab_session:
            if room.room_type != 'LAB':
                conflicts.append(
                    f"Lab session for '{entry.course.course_name}' assigned to non-lab room '{room.room_id}'"
                )
        else:
            if room.room_type == 'LAB':
                conflicts.append(
                    f"Theory session for '{entry.course.course_name}' assigned to lab room '{room.room_id}'"
                )

    return Response({
        "valid": len(conflicts) == 0,
        "total_entries": entries.count(),
        "conflicts": conflicts,
    })


@api_view(['GET'])
@permission_classes([IsHODOrAdmin])
def validate_move(request):
    """
    Real-time validation for a proposed drag-and-drop move.
    Does NOT commit any changes — purely a conflict pre-check.

    Query params:
        entry_id    - ID of the ScheduleEntry being moved
        target_day  - Target day (MON, TUE, WED, THU, FRI)
        target_slot - Target slot number (1-8)

    Returns:
        { valid: bool, conflicts: [...] }
    """
    entry_id = request.query_params.get('entry_id')
    target_day = request.query_params.get('target_day', '').upper()
    target_slot = request.query_params.get('target_slot')

    if not all([entry_id, target_day, target_slot]):
        return Response(
            {'error': 'entry_id, target_day, and target_slot are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        entry = ScheduleEntry.objects.select_related(
            'schedule', 'section', 'teacher', 'room', 'timeslot', 'course'
        ).get(id=entry_id)
    except ScheduleEntry.DoesNotExist:
        return Response({'error': 'Entry not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        target_timeslot = TimeSlot.objects.get(day=target_day, slot_number=int(target_slot))
    except TimeSlot.DoesNotExist:
        return Response({'error': f'No timeslot for {target_day} slot {target_slot}'}, status=status.HTTP_404_NOT_FOUND)

    schedule_id = entry.schedule_id
    conflicts = []

    # Exclude the entry itself when checking (it's being moved away)
    other_entries = ScheduleEntry.objects.filter(
        schedule_id=schedule_id, timeslot=target_timeslot
    ).exclude(id=entry.id).select_related('teacher', 'room', 'section', 'course')

    for other in other_entries:
        # Teacher double-booking
        if other.teacher_id == entry.teacher_id:
            conflicts.append(
                f"Teacher '{entry.teacher.teacher_name}' already has a class at "
                f"{target_day} Slot {target_slot} ({other.course.course_id})"
            )
        # Room double-booking
        if other.room_id == entry.room_id:
            conflicts.append(
                f"Room '{entry.room.room_id}' is already occupied at "
                f"{target_day} Slot {target_slot} ({other.course.course_id})"
            )
        # Section double-booking
        if other.section_id == entry.section_id:
            conflicts.append(
                f"Section '{entry.section.class_id}' already has a class at "
                f"{target_day} Slot {target_slot} ({other.course.course_id})"
            )

    return Response({
        'valid': len(conflicts) == 0,
        'conflicts': conflicts,
        'target_day': target_day,
        'target_slot': int(target_slot),
    })


@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def move_entry(request):
    """
    Atomically move a ScheduleEntry to a new timeslot.
    Uses optimistic locking via last_modified to prevent concurrent overwrites.

    Body:
        entry_id      - ID of the ScheduleEntry to move
        target_day    - Target day (MON, TUE, WED, THU, FRI)
        target_slot   - Target slot number (1-8)
        last_modified - ISO timestamp of the entry's last_modified when the drag started

    Returns:
        200 OK with updated entry on success
        409 Conflict if another admin already moved this entry
        400/404 on validation/not-found errors
    """
    from django.db import transaction
    from dateutil.parser import parse as parse_dt

    entry_id = request.data.get('entry_id')
    target_day = request.data.get('target_day', '').upper()
    target_slot = request.data.get('target_slot')
    client_last_modified = request.data.get('last_modified')

    if not all([entry_id, target_day, target_slot, client_last_modified]):
        return Response(
            {'error': 'entry_id, target_day, target_slot, and last_modified are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            # Lock the row while we work on it
            entry = ScheduleEntry.objects.select_for_update().select_related(
                'schedule', 'section', 'teacher', 'room', 'timeslot', 'course'
            ).get(id=entry_id)

            # Optimistic locking check — reject if someone else already moved it
            server_ts = entry.last_modified.isoformat()
            client_ts = parse_dt(client_last_modified).isoformat()
            if server_ts != client_ts:
                return Response(
                    {
                        'error': 'This entry was recently modified by another admin. Please refresh the timetable.',
                        'conflict_type': 'CONCURRENT_EDIT',
                    },
                    status=status.HTTP_409_CONFLICT
                )

            target_timeslot = TimeSlot.objects.get(day=target_day, slot_number=int(target_slot))

            # Conflict checks (same as validate_move)
            conflict_list = []
            other_entries = ScheduleEntry.objects.filter(
                schedule_id=entry.schedule_id, timeslot=target_timeslot
            ).exclude(id=entry.id).select_related('teacher', 'room', 'section', 'course')

            for other in other_entries:
                if other.teacher_id == entry.teacher_id:
                    conflict_list.append(
                        f"Teacher '{entry.teacher.teacher_name}' already has a class at "
                        f"{target_day} Slot {target_slot}"
                    )
                if other.room_id == entry.room_id:
                    conflict_list.append(
                        f"Room '{entry.room.room_id}' is already occupied at "
                        f"{target_day} Slot {target_slot}"
                    )
                if other.section_id == entry.section_id:
                    conflict_list.append(
                        f"Section '{entry.section.class_id}' already has a class at "
                        f"{target_day} Slot {target_slot}"
                    )

            if conflict_list:
                return Response(
                    {'error': 'Move rejected due to scheduling conflicts', 'conflicts': conflict_list},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Apply the move
            old_slot = f"{entry.timeslot.day} Slot {entry.timeslot.slot_number}"
            entry.timeslot = target_timeslot
            entry.save()  # auto_now=True on last_modified updates the timestamp

            # Write to audit log
            from core.models import AuditLog
            AuditLog.objects.using('audit_db').create(
                user_name=request.user.username,
                action='UPDATE',
                model_name='ScheduleEntry',
                object_id=str(entry.id),
                details={
                    'action': 'drag_move',
                    'course': entry.course.course_id,
                    'section': entry.section.class_id,
                    'from': old_slot,
                    'to': f"{target_day} Slot {target_slot}",
                },
            )

            from core.serializers import ScheduleEntrySerializer
            serializer = ScheduleEntrySerializer(entry)
            return Response({'success': True, 'entry': serializer.data})

    except ScheduleEntry.DoesNotExist:
        return Response({'error': 'Entry not found'}, status=status.HTTP_404_NOT_FOUND)
    except TimeSlot.DoesNotExist:
        return Response(
            {'error': f'No timeslot found for {target_day} slot {target_slot}'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def publish_schedule(request, schedule_id):
    """
    Publish a completed schedule and notify affected teachers.

    1. Sets the schedule status to PUBLISHED.
    2. Finds the previously published schedule (if any).
    3. Compares entries per teacher between old and new schedule.
    4. Creates Notification records for each teacher whose assignments changed.
    5. Logs the action in AuditLog.
    """
    from core.models import AuditLog, Notification, User

    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
    except Schedule.DoesNotExist:
        return Response(
            {"error": "Schedule not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    if schedule.status not in ('COMPLETED', 'PUBLISHED'):
        return Response(
            {"error": f"Cannot publish a schedule with status '{schedule.status}'. Only COMPLETED schedules can be published."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Find the previously published schedule (excluding the current one)
    previous_schedule = (
        Schedule.objects.filter(status='PUBLISHED')
        .exclude(schedule_id=schedule_id)
        .order_by('-completed_at', '-created_at')
        .first()
    )

    # Mark any previously published schedule as COMPLETED (only one published at a time)
    if previous_schedule:
        previous_schedule.status = 'COMPLETED'
        previous_schedule.save()

    # Set the new schedule as PUBLISHED
    schedule.status = 'PUBLISHED'
    schedule.save()

    # --- Change detection & notification creation ---
    new_entries = ScheduleEntry.objects.filter(
        schedule=schedule
    ).select_related('course', 'teacher', 'room', 'timeslot', 'section')

    # Build a dict of teacher_id -> set of entry tuples for the NEW schedule
    def build_teacher_entries_map(entries):
        """Build {teacher_id: set of (day, slot, course_id, room_id, section_id, is_lab)} tuples."""
        teacher_map = {}
        for entry in entries:
            key = (
                entry.timeslot.day,
                entry.timeslot.slot_number,
                entry.course.course_id,
                entry.room.room_id,
                entry.section.class_id,
                entry.is_lab_session,
            )
            teacher_map.setdefault(entry.teacher.teacher_id, set()).add(key)
        return teacher_map

    new_map = build_teacher_entries_map(new_entries)
    notifications_created = 0
    teacher_messages = {} # Collect messages for emails

    # Save the snapshot to the current schedule so future publishes can compare against it
    snapshot_data = {}
    for teacher_id, entries_set in new_map.items():
        snapshot_data[teacher_id] = [
            {
                'day': e[0], 
                'slot': e[1], 
                'course': e[2], 
                'room': e[3], 
                'section': e[4], 
                'is_lab': e[5]
            } for e in entries_set
        ]
    schedule.published_snapshot = snapshot_data
    schedule.save(update_fields=['published_snapshot'])

    if previous_schedule:
        # Compare against old schedule using its frozen snapshot
        old_map = {}
        if previous_schedule.published_snapshot:
            for teacher_id, entries_list in previous_schedule.published_snapshot.items():
                old_map[teacher_id] = set(
                    (e['day'], e['slot'], e['course'], e['room'], e['section'], e['is_lab'])
                    for e in entries_list
                )
        else:
            # Fallback for schedules published before this feature was added
            old_entries = ScheduleEntry.objects.filter(
                schedule=previous_schedule
            ).select_related('course', 'teacher', 'room', 'timeslot', 'section')
            old_map = build_teacher_entries_map(old_entries)

        # Find all teachers in either old or new schedule
        all_teacher_ids = set(new_map.keys()) | set(old_map.keys())

        for teacher_id in all_teacher_ids:
            old_set = old_map.get(teacher_id, set())
            new_set = new_map.get(teacher_id, set())

            if old_set != new_set:
                # This teacher's schedule changed — find their User account
                users = User.objects.filter(teacher__teacher_id=teacher_id)
                if not users.exists():
                    continue

                # Build change summary
                added = new_set - old_set
                removed = old_set - new_set

                day_names = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday', 'THU': 'Thursday', 'FRI': 'Friday'}
                changes = []
                if added:
                    for day, slot, course, room, section, is_lab in sorted(added):
                        session_type = "Lab" if is_lab else "Lecture"
                        changes.append(f"+ {day_names.get(day, day)} Slot {slot}: {course} ({session_type}) in {room} for {section}")
                if removed:
                    for day, slot, course, room, section, is_lab in sorted(removed):
                        session_type = "Lab" if is_lab else "Lecture"
                        changes.append(f"- {day_names.get(day, day)} Slot {slot}: {course} ({session_type}) in {room} for {section}")

                message = "Changes to your timetable:\n" + "\n".join(changes)
                teacher_messages[teacher_id] = message

                for user in users:
                    Notification.objects.create(
                        recipient=user,
                        schedule=schedule,
                        title=f"Timetable Updated: {schedule.name}",
                        message=message,
                    )
                    notifications_created += 1
    else:
        # First publish — notify all teachers in the schedule
        for teacher_id in new_map.keys():
            users = User.objects.filter(teacher__teacher_id=teacher_id)
            if not users.exists():
                continue
                
            entries_summary = []
            day_names = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday', 'THU': 'Thursday', 'FRI': 'Friday'}
            for day, slot, course, room, section, is_lab in sorted(new_map[teacher_id]):
                session_type = "Lab" if is_lab else "Lecture"
                entries_summary.append(f"• {day_names.get(day, day)} Slot {slot}: {course} ({session_type}) in {room} for {section}")

            message = "Your timetable has been published:\n" + "\n".join(entries_summary)
            teacher_messages[teacher_id] = message

            for user in users:
                Notification.objects.create(
                    recipient=user,
                    schedule=schedule,
                    title=f"New Timetable Published: {schedule.name}",
                    message=message,
                )
                notifications_created += 1

    # --- Trigger Email Notifications (Synchronous) ---
    send_publish_notifications(schedule.schedule_id, custom_messages=teacher_messages)

    # Audit log
    AuditLog.objects.using('audit_db').create(
        user_name=request.user.username,
        action='UPDATE',
        model_name='Schedule',
        object_id=str(schedule.schedule_id),
        details={
            'action': 'publish',
            'schedule_name': schedule.name,
            'notifications_sent': notifications_created,
            'had_previous': previous_schedule is not None,
        },
    )

    return Response({
        "status": "published",
        "schedule_id": schedule.schedule_id,
        "notifications_sent": notifications_created,
        "message": f"Schedule '{schedule.name}' published successfully. {notifications_created} teacher(s) notified.",
    })


@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def send_reminders(request):
    """
    Triggers the background task to send deadline reminder emails to faculty.
    """
    targeted = request.query_params.get("targeted", "false").lower() == "true"
    result_msg = send_deadline_reminders(targeted=targeted)
    
    msg = (
        f"Targeted reminder emails sent: {result_msg}"
        if targeted
        else f"Deadline reminder emails sent: {result_msg}"
    )
    return Response({
        "success": True,
        "message": msg,
        "targeted": targeted,
    })

