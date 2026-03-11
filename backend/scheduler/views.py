"""
Scheduler API Views

This module provides API endpoints for schedule generation and analytics.
- Safe handling of null rooms for Project Phases.
- Distinct timeslot counting to prevent double-counting in analytics.
- Elective group overlap conflict exceptions.

Author: M3 Backend Team
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
    Tries Celery async first, falls back to synchronous execution if broker is unavailable.
    """
    name = request.data.get('name', 'Untitled Schedule')
    semester = request.data.get('semester')
    year = request.data.get('year')  # Optional — None means all years

    if not semester:
        return Response(
            {"error": "semester is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Create schedule object
    schedule = Schedule.objects.create(
        name=name,
        semester=semester,
        year=year,
        status='PENDING'
    )

    # Try Celery async; fall back to synchronous on broker errors
    try:
        generate_schedule_async.delay(schedule.schedule_id)
        async_mode = True
    except Exception:
        # Celery broker not available — run synchronously
        from .algorithm import generate_schedule as run_sync
        try:
            run_sync(schedule.schedule_id)
        except Exception as e:
            schedule.status = 'FAILED'
            schedule.save()
            return Response(
                {"error": f"Schedule generation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        async_mode = False

    serializer = ScheduleSerializer(schedule)

    return Response({
        "schedule_id": schedule.schedule_id,
        "status": schedule.status,
        "message": (
            "Schedule generation queued successfully and is processing in the background."
            if async_mode else
            "Schedule generated synchronously (Celery not running)."
        ),
        "data": serializer.data
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([IsHODOrAdmin])
def get_schedule_status(request, schedule_id):
    """
    Check the current status of a schedule generation task.
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
        serializer = ScheduleSerializer(schedule)
        return Response(serializer.data)
    except Schedule.DoesNotExist:
        return Response(
            {"error": "Schedule not found"},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsFacultyOrAbove])
def get_workload_analytics(request):
    """
    Get faculty workload analytics.
    Counts distinct timeslots to prevent double counting parallel sections.
    """
    schedule_id = request.query_params.get('schedule_id')
    
    if not schedule_id:
        return Response({"error": "schedule_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get workload data
    workload_data = ScheduleEntry.objects.filter(
        schedule_id=schedule_id
    ).values(
        'teacher__teacher_id',
        'teacher__teacher_name',
        'teacher__max_hours_per_week'
    ).annotate(
        total_hours=Count('timeslot_id', distinct=True) # DISTINCT to prevent double counting
    )
    
    # Calculate utilization
    result = []
    for item in workload_data:
        max_hrs = item['teacher__max_hours_per_week'] or 1
        utilization = (item['total_hours'] / max_hrs) * 100
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
    Counts distinct timeslots to prevent double counting parallel sections.
    """
    schedule_id = request.query_params.get('schedule_id')
    
    if not schedule_id:
        return Response({"error": "schedule_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    total_slots = 40 # 5 days * 8 slots
    
    # Get room utilization data
    room_data = ScheduleEntry.objects.filter(
        schedule_id=schedule_id
    ).values(
        'room__room_id',
        'room__room_type'
    ).annotate(
        total_slots_used=Count('timeslot_id', distinct=True) # DISTINCT to prevent double counting
    )
    
    # Calculate utilization
    result = []
    for item in room_data:
        if not item['room__room_id']: continue # Skip Null rooms (Project Phases)
            
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
    """
    schedule_id = request.query_params.get('schedule_id')
    section_id = request.query_params.get('section')
    teacher_id = request.query_params.get('teacher')
    course_id = request.query_params.get('course')
    room_id = request.query_params.get('room')
    
    if not schedule_id:
        return Response({"error": "schedule_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    query = ScheduleEntry.objects.filter(schedule_id=schedule_id)
    
    if section_id: query = query.filter(section_id=section_id)
    if teacher_id: query = query.filter(teacher_id=teacher_id)
    if course_id: query = query.filter(course_id=course_id)
    if room_id: query = query.filter(room_id=room_id)
    
    entries = query.select_related(
        'section', 'course', 'teacher', 'room', 'timeslot'
    ).order_by('timeslot__day', 'timeslot__slot_number')
    
    timetable = {}
    for entry in entries:
        day = entry.timeslot.day
        slot_num = entry.timeslot.slot_number
        
        if day not in timetable: timetable[day] = {}
        if slot_num not in timetable[day]: timetable[day][slot_num] = []
        
        timetable[day][slot_num].append({
            'entry_id': entry.id,
            'course_code': entry.course.course_id,
            'course_name': entry.course.course_name,
            'teacher_id': entry.teacher.teacher_id,
            'teacher_name': entry.teacher.teacher_name,
            'room': entry.room.room_id if entry.room else 'TBA',
            'section': entry.section.class_id,
            'is_lab_session': entry.is_lab_session,
            'is_adm': entry.course.is_adm,
            'is_elective': entry.course.is_elective,
            'year': entry.course.year,
            'session_type': entry.session_type,
            'elective_group': entry.course.elective_group,
            'elective_type': entry.course.elective_type,
            'start_time': entry.timeslot.start_time.strftime('%H:%M'),
            'end_time': entry.timeslot.end_time.strftime('%H:%M'),
            'timeslot_id': entry.timeslot_id,
            'constraint_reason': entry.constraint_reason,
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
    
    if not hasattr(user, 'teacher') or not user.teacher:
        return Response({"error": "No teacher record linked to this account"}, status=status.HTTP_400_BAD_REQUEST)
        
    teacher_id = user.teacher.teacher_id
    schedule_id = request.query_params.get('schedule_id')
    
    if not schedule_id:
        latest_schedule = Schedule.objects.filter(status='COMPLETED').order_by('-created_at').first()
        if latest_schedule: schedule_id = latest_schedule.schedule_id
            
    if not schedule_id:
        return Response({"error": "No generated schedules found"}, status=status.HTTP_404_NOT_FOUND)
        
    entries = ScheduleEntry.objects.filter(
        schedule_id=schedule_id,
        teacher_id=teacher_id
    ).select_related(
        'section', 'course', 'teacher', 'room', 'timeslot'
    ).order_by('timeslot__day', 'timeslot__slot_number')
    
    timetable = {}
    for entry in entries:
        day = entry.timeslot.day
        slot_num = entry.timeslot.slot_number
        
        if day not in timetable: timetable[day] = {}
        if slot_num not in timetable[day]: timetable[day][slot_num] = []
        
        timetable[day][slot_num].append({
            'course_code': entry.course.course_id,
            'course_name': entry.course.course_name,
            'teacher_name': entry.teacher.teacher_name,
            'room': entry.room.room_id if entry.room else 'TBA',
            'section': entry.section.class_id,
            'is_lab_session': entry.is_lab_session,
            'is_adm': entry.course.is_adm,
            'is_elective': entry.course.is_elective,
            'year': entry.course.year,
            'session_type': entry.session_type,
            'elective_group': entry.course.elective_group,
            'elective_type': entry.course.elective_type,
            'start_time': entry.timeslot.start_time.strftime('%H:%M'),
            'end_time': entry.timeslot.end_time.strftime('%H:%M'),
            'constraint_reason': entry.constraint_reason,
            'timeslot_id': entry.timeslot_id,
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
    """
    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
    except Schedule.DoesNotExist:
        return Response({"error": "Schedule not found"}, status=status.HTTP_404_NOT_FOUND)

    conflicts = []
    entries = ScheduleEntry.objects.filter(schedule=schedule)

    # 1. Teacher double-booking
    teacher_clashes = (
        entries.values('teacher', 'timeslot')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )
    for c in teacher_clashes:
        overlapping_entries = entries.filter(teacher=c['teacher'], timeslot=c['timeslot']).select_related('course')
        course_ids = set()
        elective_groups = set()
        
        for e in overlapping_entries:
            course_ids.add(e.course.course_id)
            if e.course.elective_group and e.course.elective_group != 'NA':
                elective_groups.add(e.course.elective_group)
                
        is_conflict = True
        if len(course_ids) == 1:
            is_conflict = False
        elif len(elective_groups) == 1 and len(course_ids) > 1:
            if all(e.course.elective_group and e.course.elective_group != 'NA' for e in overlapping_entries):
                is_conflict = False
                
        if is_conflict:
            t = Teacher.objects.get(pk=c['teacher'])
            ts = TimeSlot.objects.get(pk=c['timeslot'])
            check_count = c['count']
            conflicts.append(
                f"Teacher '{t.teacher_name}' is assigned {check_count} distinct classes at {ts.day} Slot {ts.slot_number}"
            )

    # 2. Room double-booking (excluding null rooms)
    room_clashes = (
        entries.exclude(room__isnull=True)
        .values('room', 'timeslot')
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
        overlapping_entries = entries.filter(section=c['section'], timeslot=c['timeslot']).select_related('course')
        elective_groups = set()
        
        for e in overlapping_entries:
            if e.course.elective_group and e.course.elective_group != 'NA':
                elective_groups.add(e.course.elective_group)
            else:
                elective_groups.add(None) 
                
        is_conflict = True
        if len(elective_groups) == 1 and list(elective_groups)[0] is not None:
            is_conflict = False
            
        if is_conflict:
            s = Section.objects.get(pk=c['section'])
            ts = TimeSlot.objects.get(pk=c['timeslot'])
            check_count = c['count']
            conflicts.append(
                f"Section '{s.class_id}' has {check_count} classes at {ts.day} Slot {ts.slot_number}"
            )

    # 4. Room-type mismatch
    for entry in entries.select_related('course', 'room'):
        room = entry.room
        if not room: continue 
        if entry.is_lab_session:
            if room.room_type != 'LAB':
                conflicts.append(f"Lab session for '{entry.course.course_name}' assigned to non-lab room '{room.room_id}'")
        else:
            if room.room_type == 'LAB':
                conflicts.append(f"Theory session for '{entry.course.course_name}' assigned to lab room '{room.room_id}'")

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
    """
    entry_id = request.query_params.get('entry_id')
    target_day = request.query_params.get('target_day', '').upper()
    target_slot = request.query_params.get('target_slot')

    if not all([entry_id, target_day, target_slot]):
        return Response({'error': 'entry_id, target_day, and target_slot are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        entry = ScheduleEntry.objects.select_related('schedule', 'section', 'teacher', 'room', 'timeslot', 'course').get(id=entry_id)
    except ScheduleEntry.DoesNotExist:
        return Response({'error': 'Entry not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        target_timeslot = TimeSlot.objects.get(day=target_day, slot_number=int(target_slot))
    except TimeSlot.DoesNotExist:
        return Response({'error': f'No timeslot for {target_day} slot {target_slot}'}, status=status.HTTP_404_NOT_FOUND)

    schedule_id = entry.schedule_id
    conflicts = []

    other_entries = ScheduleEntry.objects.filter(schedule_id=schedule_id, timeslot=target_timeslot).exclude(id=entry.id).select_related('teacher', 'room', 'section', 'course')

    for other in other_entries:
        if other.teacher_id == entry.teacher_id:
            is_conflict = True
            if other.course_id == entry.course_id:
                is_conflict = False
            elif getattr(other.course, 'elective_group', None) and other.course.elective_group != 'NA' and getattr(entry.course, 'elective_group', None) == other.course.elective_group:
                is_conflict = False
            if is_conflict:
                conflicts.append(f"Teacher '{entry.teacher.teacher_name}' already has a different class at {target_day} Slot {target_slot} ({other.course.course_id})")
                
        if other.room_id and entry.room_id and other.room_id == entry.room_id:
            conflicts.append(f"Room '{entry.room.room_id}' is already occupied at {target_day} Slot {target_slot} ({other.course.course_id})")
            
        if other.section_id == entry.section_id:
            is_conflict = True
            other_group = getattr(other.course, 'elective_group', None)
            entry_group = getattr(entry.course, 'elective_group', None)
            if other_group and other_group != 'NA' and entry_group == other_group:
                is_conflict = False
            if is_conflict:
                conflicts.append(f"Section '{entry.section.class_id}' already has a class at {target_day} Slot {target_slot}")

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
    Uses optimistic locking.
    """
    from django.db import transaction
    from dateutil.parser import parse as parse_dt

    entry_id = request.data.get('entry_id')
    target_day = request.data.get('target_day', '').upper()
    target_slot = request.data.get('target_slot')
    client_last_modified = request.data.get('last_modified')

    if not all([entry_id, target_day, target_slot, client_last_modified]):
        return Response({'error': 'entry_id, target_day, target_slot, and last_modified are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            entry = ScheduleEntry.objects.select_for_update().select_related('schedule', 'section', 'teacher', 'room', 'timeslot', 'course').get(id=entry_id)

            server_ts = entry.last_modified.isoformat()
            client_ts = parse_dt(client_last_modified).isoformat()
            if server_ts != client_ts:
                return Response({'error': 'This entry was recently modified by another admin. Please refresh the timetable.', 'conflict_type': 'CONCURRENT_EDIT'}, status=status.HTTP_409_CONFLICT)

            target_timeslot = TimeSlot.objects.get(day=target_day, slot_number=int(target_slot))
            conflict_list = []
            other_entries = ScheduleEntry.objects.filter(schedule_id=entry.schedule_id, timeslot=target_timeslot).exclude(id=entry.id).select_related('teacher', 'room', 'section', 'course')

            for other in other_entries:
                if other.teacher_id == entry.teacher_id:
                    is_conflict = True
                    if other.course_id == entry.course_id:
                        is_conflict = False
                    elif getattr(other.course, 'elective_group', None) and other.course.elective_group != 'NA' and getattr(entry.course, 'elective_group', None) == other.course.elective_group:
                        is_conflict = False
                    if is_conflict:
                        conflict_list.append(f"Teacher '{entry.teacher.teacher_name}' already has a different class at {target_day} Slot {target_slot}")
                        
                if other.room_id and entry.room_id and other.room_id == entry.room_id:
                    conflict_list.append(f"Room '{entry.room.room_id}' is already occupied at {target_day} Slot {target_slot}")
                    
                if other.section_id == entry.section_id:
                    is_conflict = True
                    other_group = getattr(other.course, 'elective_group', None)
                    entry_group = getattr(entry.course, 'elective_group', None)
                    if other_group and other_group != 'NA' and entry_group == other_group:
                        is_conflict = False
                    if is_conflict:
                        conflict_list.append(f"Section '{entry.section.class_id}' already has a class at {target_day} Slot {target_slot}")

            if conflict_list:
                return Response({'error': 'Move rejected due to scheduling conflicts', 'conflicts': conflict_list}, status=status.HTTP_400_BAD_REQUEST)

            old_slot = f"{entry.timeslot.day} Slot {entry.timeslot.slot_number}"
            entry.timeslot = target_timeslot
            entry.save() 

            from core.models import AuditLog
            AuditLog.objects.using('audit_db').create(
                user_name=request.user.username,
                action='UPDATE',
                model_name='ScheduleEntry',
                object_id=str(entry.id),
                details={'action': 'drag_move', 'course': entry.course.course_id, 'section': entry.section.class_id, 'from': old_slot, 'to': f"{target_day} Slot {target_slot}"},
            )

            from core.serializers import ScheduleEntrySerializer
            serializer = ScheduleEntrySerializer(entry)
            return Response({'success': True, 'entry': serializer.data})

    except ScheduleEntry.DoesNotExist:
        return Response({'error': 'Entry not found'}, status=status.HTTP_404_NOT_FOUND)
    except TimeSlot.DoesNotExist:
        return Response({'error': f'No timeslot found for {target_day} slot {target_slot}'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsHODOrAdmin])
def publish_schedule(request, schedule_id):
    """
    Publish a completed schedule and notify affected teachers.
    """
    from core.models import AuditLog, Notification, User

    try:
        schedule = Schedule.objects.get(schedule_id=schedule_id)
    except Schedule.DoesNotExist:
        return Response({"error": "Schedule not found"}, status=status.HTTP_404_NOT_FOUND)

    if schedule.status not in ('COMPLETED', 'PUBLISHED'):
        return Response({"error": f"Cannot publish a schedule with status '{schedule.status}'. Only COMPLETED schedules can be published."}, status=status.HTTP_400_BAD_REQUEST)

    previous_schedule = Schedule.objects.filter(status='PUBLISHED').exclude(schedule_id=schedule_id).order_by('-completed_at', '-created_at').first()

    if previous_schedule:
        previous_schedule.status = 'COMPLETED'
        previous_schedule.save()

    schedule.status = 'PUBLISHED'
    schedule.save()

    new_entries = ScheduleEntry.objects.filter(schedule=schedule).select_related('course', 'teacher', 'room', 'timeslot', 'section')

    def build_teacher_entries_map(entries):
        teacher_map = {}
        for entry in entries:
            key = (
                entry.timeslot.day,
                entry.timeslot.slot_number,
                entry.course.course_id,
                entry.room.room_id if entry.room else 'TBA',
                entry.section.class_id,
                entry.is_lab_session,
            )
            teacher_map.setdefault(entry.teacher.teacher_id, set()).add(key)
        return teacher_map

    new_map = build_teacher_entries_map(new_entries)
    notifications_created = 0
    teacher_messages = {} 

    snapshot_data = {}
    for teacher_id, entries_set in new_map.items():
        snapshot_data[teacher_id] = [{'day': e[0], 'slot': e[1], 'course': e[2], 'room': e[3], 'section': e[4], 'is_lab': e[5]} for e in entries_set]
    schedule.published_snapshot = snapshot_data
    schedule.save(update_fields=['published_snapshot'])

    if previous_schedule:
        old_map = {}
        if previous_schedule.published_snapshot:
            for teacher_id, entries_list in previous_schedule.published_snapshot.items():
                old_map[teacher_id] = set((e['day'], e['slot'], e['course'], e['room'], e['section'], e['is_lab']) for e in entries_list)
        else:
            old_entries = ScheduleEntry.objects.filter(schedule=previous_schedule).select_related('course', 'teacher', 'room', 'timeslot', 'section')
            old_map = build_teacher_entries_map(old_entries)

        all_teacher_ids = set(new_map.keys()) | set(old_map.keys())

        for teacher_id in all_teacher_ids:
            old_set = old_map.get(teacher_id, set())
            new_set = new_map.get(teacher_id, set())

            if old_set != new_set:
                users = User.objects.filter(teacher__teacher_id=teacher_id)
                if not users.exists(): continue

                added = new_set - old_set
                removed = old_set - new_set

                day_names = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday', 'THU': 'Thursday', 'FRI': 'Friday'}
                changes = []
                if added:
                    for day, slot, course, room, section, is_lab in sorted(added):
                        changes.append(f"+ {day_names.get(day, day)} Slot {slot}: {course} ({'Lab' if is_lab else 'Lecture'}) in {room} for {section}")
                if removed:
                    for day, slot, course, room, section, is_lab in sorted(removed):
                        changes.append(f"- {day_names.get(day, day)} Slot {slot}: {course} ({'Lab' if is_lab else 'Lecture'}) in {room} for {section}")

                message = "Changes to your timetable:\n" + "\n".join(changes)
                teacher_messages[teacher_id] = message

                for user in users:
                    Notification.objects.create(recipient=user, schedule=schedule, title=f"Timetable Updated: {schedule.name}", message=message)
                    notifications_created += 1
    else:
        for teacher_id in new_map.keys():
            users = User.objects.filter(teacher__teacher_id=teacher_id)
            if not users.exists(): continue
                
            entries_summary = []
            day_names = {'MON': 'Monday', 'TUE': 'Tuesday', 'WED': 'Wednesday', 'THU': 'Thursday', 'FRI': 'Friday'}
            for day, slot, course, room, section, is_lab in sorted(new_map[teacher_id]):
                entries_summary.append(f"• {day_names.get(day, day)} Slot {slot}: {course} ({'Lab' if is_lab else 'Lecture'}) in {room} for {section}")

            message = "Your timetable has been published:\n" + "\n".join(entries_summary)
            teacher_messages[teacher_id] = message

            for user in users:
                Notification.objects.create(recipient=user, schedule=schedule, title=f"New Timetable Published: {schedule.name}", message=message)
                notifications_created += 1

    send_publish_notifications(schedule.schedule_id, custom_messages=teacher_messages)

    AuditLog.objects.using('audit_db').create(
        user_name=request.user.username,
        action='UPDATE',
        model_name='Schedule',
        object_id=str(schedule.schedule_id),
        details={'action': 'publish', 'schedule_name': schedule.name, 'notifications_sent': notifications_created, 'had_previous': previous_schedule is not None},
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
    
    return Response({
        "success": True,
        "message": f"Targeted reminder emails sent: {result_msg}" if targeted else f"Deadline reminder emails sent: {result_msg}",
        "targeted": targeted,
    })