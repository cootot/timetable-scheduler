"""
API Views for M3 Timetable Scheduling System

This module contains all API ViewSets for CRUD operations on core models.
Uses Django REST Framework's ViewSet pattern for clean, RESTful APIs.

Author: Backend Team (Vamsi, Akshitha)
Sprint: 1
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Q
from django.db import transaction
from django.utils import timezone
from .models import (
    User, Teacher, Course, Room, TimeSlot, Section,
    TeacherCourseMapping, Schedule, ScheduleEntry,
    Constraint, ConflictLog, ChangeRequest, Notification
)
from .serializers import (
    TeacherSerializer, CourseSerializer, RoomSerializer,
    TimeSlotSerializer, SectionSerializer, TeacherCourseMappingSerializer,
    ScheduleSerializer, ScheduleDetailSerializer, ScheduleEntrySerializer,
    ConstraintSerializer, ConflictLogSerializer, ChangeRequestSerializer,
    NotificationSerializer
)
from accounts.permissions import IsAdmin, IsHODOrAdmin, IsFacultyOrAbove


class TeacherViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Teacher CRUD operations.
    """
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    pagination_class = None
    
    def get_permissions(self):
        """
        Allow read access to authenticated users, write access to HOD/Admin.
        """
        if self.action in ['list', 'retrieve', 'by_department']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Get teachers grouped by department"""
        # If HOD, filter by their department automatically? 
        # For now, just trust the query param or show all if Admin
        department = request.query_params.get('department', None)
        if department:
            teachers = Teacher.objects.filter(department=department)
        else:
            teachers = Teacher.objects.all()
        
        serializer = self.get_serializer(teachers, many=True)
        return Response(serializer.data)


class CourseViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Course CRUD operations.
    """
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    pagination_class = None
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_year', 'by_semester']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def by_year(self, request):
        """Filter courses by year"""
        year = request.query_params.get('year', None)
        if year:
            courses = Course.objects.filter(year=int(year))
        else:
            courses = Course.objects.all()
        
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_semester(self, request):
        """Filter courses by semester"""
        semester = request.query_params.get('semester', None)
        if semester:
            courses = Course.objects.filter(semester=semester)
        else:
            courses = Course.objects.all()
        
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Filter courses by department"""
        # Note: Course model doesn't have department field directly
        # For now, return all courses or implement logic based on course_id prefix
        courses = Course.objects.all()
        
        serializer = self.get_serializer(courses, many=True)
        return Response(serializer.data)


class RoomViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Room CRUD operations.
    """
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    pagination_class = None
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_type']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Filter rooms by type"""
        room_type = request.query_params.get('type', None)
        if room_type:
            rooms = Room.objects.filter(room_type=room_type)
        else:
            rooms = Room.objects.all()
        
        serializer = self.get_serializer(rooms, many=True)
        return Response(serializer.data)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """
    API endpoint for TimeSlot operations.
    """
    queryset = TimeSlot.objects.all()
    serializer_class = TimeSlotSerializer
    pagination_class = None
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_day']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def by_day(self, request):
        """Filter time slots by day"""
        day = request.query_params.get('day', None)
        if day:
            slots = TimeSlot.objects.filter(day=day.upper())
        else:
            slots = TimeSlot.objects.all()
        
        serializer = self.get_serializer(slots, many=True)
        return Response(serializer.data)


class SectionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Section CRUD operations.
    """
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    pagination_class = None
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_year']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def by_year(self, request):

        """Filter sections by year"""
        year = request.query_params.get('year', None)
        if year:
            sections = Section.objects.filter(year=int(year))
        else:
            sections = Section.objects.all()
        
        serializer = self.get_serializer(sections, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_department(self, request):
        """Filter sections by department"""
        department = request.query_params.get('department', None)
        if department:
            sections = Section.objects.filter(department=department)
        else:
            sections = Section.objects.all()
        
        serializer = self.get_serializer(sections, many=True)
        return Response(serializer.data)


class TeacherCourseMappingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for TeacherCourseMapping CRUD operations.
    """
    queryset = TeacherCourseMapping.objects.all()
    serializer_class = TeacherCourseMappingSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'by_teacher']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def by_teacher(self, request):
        """Filter mappings by teacher ID"""
        teacher_id = request.query_params.get('teacher_id', None)
        if teacher_id:
            mappings = TeacherCourseMapping.objects.filter(teacher_id=teacher_id)
        else:
            mappings = TeacherCourseMapping.objects.all()
        
        serializer = self.get_serializer(mappings, many=True)
        return Response(serializer.data)


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Schedule operations.
    """
    queryset = Schedule.objects.all()
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == 'retrieve':
            return ScheduleDetailSerializer
        return ScheduleSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'entries', 'conflicts']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'])
    def entries(self, request, pk=None):
        """Get all schedule entries for a specific schedule"""
        schedule = self.get_object()
        entries = schedule.entries.all()
        serializer = ScheduleEntrySerializer(entries, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        """Get all conflicts for a specific schedule"""
        schedule = self.get_object()
        conflicts = schedule.conflicts.all()
        serializer = ConflictLogSerializer(conflicts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def filters(self, request, pk=None):
        """Get unique sections, teachers, courses, and rooms used in this schedule"""
        schedule = self.get_object()
        entries = schedule.entries.all()
        
        sections = entries.values('section_id', 'section__class_id').distinct()
        teachers = entries.values('teacher_id', 'teacher__teacher_name').distinct()
        courses = entries.values('course_id', 'course__course_name').distinct()
        rooms = entries.values('room_id', 'room__block').distinct()
        
        return Response({
            'sections': [{'class_id': s['section__class_id']} for s in sections],
            'teachers': [{'teacher_id': t['teacher_id'], 'teacher_name': t['teacher__teacher_name']} for t in teachers],
            'courses': [{'course_id': c['course_id'], 'course_name': c['course__course_name']} for c in courses],
            'rooms': [{'room_id': r['room_id'], 'block': r['room__block']} for r in rooms]
        })

    @action(detail=True, methods=['get'])
    def available_faculty(self, request, pk=None):
        """
        Find faculty available during ALL timeslots for a specific course/section.
        """
        course_id = request.query_params.get('course_id')
        section_id = request.query_params.get('section_id')
        
        if not all([course_id, section_id]):
            return Response({'error': 'Missing course_id or section_id'}, status=400)
            
        # 1. Find all timeslots where this course/section is scheduled in this schedule
        target_slots = ScheduleEntry.objects.filter(
            schedule_id=pk,
            course_id=course_id,
            section_id=section_id
        ).values_list('timeslot_id', flat=True)
        
        if not target_slots:
            return Response({'error': 'No entries found for this course/section in this schedule'}, status=404)
            
        # 2. Find teachers who are ALREADY busy in ANY of these timeslots
        busy_teacher_ids = ScheduleEntry.objects.filter(
            schedule_id=pk,
            timeslot_id__in=target_slots
        ).values_list('teacher_id', flat=True).distinct()
        
        # 3. Join with TeacherCourseMapping to ensure they CAN teach this course
        qualified_teacher_ids = TeacherCourseMapping.objects.filter(
            course_id=course_id
        ).values_list('teacher_id', flat=True)
        
        # 4. Result: Qualified teachers who are NOT busy in ANY of the target slots
        available_teachers = Teacher.objects.filter(
            teacher_id__in=qualified_teacher_ids
        ).exclude(
            teacher_id__in=busy_teacher_ids
        )
        
        serializer = TeacherSerializer(available_teachers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def swap_faculty(self, request, pk=None):
        """
        Directly swap faculty for a specific course/section across the entire schedule.
        Admin only. Immediate effect.
        """
        course_id = request.data.get('course_id')
        section_id = request.data.get('section_id')
        new_teacher_id = request.data.get('new_teacher_id')
        
        if not all([course_id, section_id, new_teacher_id]):
            return Response({'error': 'Missing course_id, section_id, or new_teacher_id'}, status=400)
            
        try:
            with transaction.atomic():
                new_teacher = Teacher.objects.get(teacher_id=new_teacher_id)
                
                # 1. Update EVERY ScheduleEntry for this course/section in this schedule
                updated_entries = ScheduleEntry.objects.filter(
                    schedule_id=pk,
                    course_id=course_id,
                    section_id=section_id
                ).update(teacher=new_teacher)
                
                # 2. Update/Create TeacherCourseMapping for persistence
                mapping_updated = TeacherCourseMapping.objects.filter(
                    course_id=course_id,
                    section_id=section_id
                ).update(teacher=new_teacher)
                
                if not mapping_updated:
                    course = Course.objects.get(course_id=course_id)
                    TeacherCourseMapping.objects.create(
                        teacher=new_teacher,
                        course_id=course_id,
                        section_id=section_id,
                        year=course.year,
                        preference_level=2
                    )
                
                return Response({
                    'message': f'Successfully swapped faculty. {updated_entries} slots updated.',
                    'updated_entries': updated_entries
                })
        except Teacher.DoesNotExist:
            return Response({'error': f'Teacher {new_teacher_id} not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class ScheduleEntryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for ScheduleEntry operations.
    """
    queryset = ScheduleEntry.objects.all()
    serializer_class = ScheduleEntrySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]


class ConstraintViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Constraint operations.
    """
    queryset = Constraint.objects.all()
    serializer_class = ConstraintSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'active']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsAdmin]
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get only active constraints"""
        constraints = Constraint.objects.filter(is_active=True)
        serializer = self.get_serializer(constraints, many=True)
        return Response(serializer.data)


from .models import (
    Teacher, Course, Room, TimeSlot, Section,
    TeacherCourseMapping, Schedule, ScheduleEntry,
    Constraint, ConflictLog, AuditLog
)
from .serializers import (
    TeacherSerializer, CourseSerializer, RoomSerializer,
    TimeSlotSerializer, SectionSerializer, TeacherCourseMappingSerializer,
    ScheduleSerializer, ScheduleDetailSerializer, ScheduleEntrySerializer,
    ConstraintSerializer, ConflictLogSerializer, AuditLogSerializer
)

# ... (existing code)

class ConflictLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for ConflictLog (Read-only).
    """
    queryset = ConflictLog.objects.all()
    serializer_class = ConflictLogSerializer
    permission_classes = [IsHODOrAdmin]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Audit Logs (Read-only).
    Admin/HOD can view logs.
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsHODOrAdmin]
    filterset_fields = ['action', 'model_name', 'user']
    search_fields = ['details', 'object_id']




class ChangeRequestViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Change Requests.
    
    HODs can create requests to modify Teacher data.
    Admins can approve/reject these requests.
    """
    queryset = ChangeRequest.objects.all()
    serializer_class = ChangeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter queryset based on user role.
        - Admin: See all requests
        - HOD: See only their own requests
        - Faculty: No access
        """
        user = self.request.user
        if user.role == 'ADMIN':
            return ChangeRequest.objects.all()
        elif user.role == 'HOD':
            return ChangeRequest.objects.filter(requested_by=user)
        return ChangeRequest.objects.none()
    
    def perform_create(self, serializer):
        """Automatically set requested_by to current user and notify admins"""
        change_request = serializer.save(requested_by=self.request.user)
        
        # Notify all Admins about the new request
        admins = User.objects.filter(role='ADMIN')
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                title="New Faculty Change Request",
                message=f"HOD {self.request.user.username} has submitted a {change_request.change_type} request for {change_request.target_model} {change_request.target_id or '(New)'}."
            )
    
    @action(detail=False, methods=['get'])
    def pending_count(self, request):
        """Get count of pending requests for the current user."""
        count = self.get_queryset().filter(status='PENDING').count()
        return Response({'count': count})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        """
        Approve a change request and apply the changes to the database.
        Admin only.
        """
        change_request = self.get_object()
        
        if change_request.status != 'PENDING':
            return Response(
                {'error': 'Only pending requests can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.db import transaction
        try:
            with transaction.atomic():
                if change_request.target_model == 'Teacher':
                    # ... [existing teacher logic] ...
                    if change_request.change_type == 'UPDATE':
                        teacher = Teacher.objects.get(teacher_id=change_request.target_id)
                        proposed_data = change_request.proposed_data.copy()
                        mappings = proposed_data.pop('mappings', None)
                        for key, value in proposed_data.items():
                            if hasattr(teacher, key):
                                setattr(teacher, key, value)
                        teacher.save()
                        if mappings is not None:
                            TeacherCourseMapping.objects.filter(teacher=teacher).delete()
                            for m_data in mappings:
                                course = Course.objects.get(course_id=m_data['course_id'])
                                TeacherCourseMapping.objects.create(
                                    teacher=teacher, course=course,
                                    section_id=m_data.get('section_id'),
                                    year=m_data.get('year') or course.year,
                                    preference_level=2
                                )
                    elif change_request.change_type == 'CREATE':
                        proposed_data = change_request.proposed_data.copy()
                        mappings = proposed_data.pop('mappings', None)
                        teacher = Teacher.objects.create(**proposed_data)
                        if mappings:
                            for m_data in mappings:
                                course = Course.objects.get(course_id=m_data['course_id'])
                                TeacherCourseMapping.objects.create(
                                    teacher=teacher, course=course,
                                    section_id=m_data.get('section_id'),
                                    year=m_data.get('year') or course.year,
                                    preference_level=2
                                )
                    elif change_request.change_type == 'DELETE':
                        teacher = Teacher.objects.get(teacher_id=change_request.target_id)
                        teacher.delete()

                elif change_request.change_type == 'SWAP':
                    proposed = change_request.proposed_data
                    entry_id = proposed.get('entry_id')
                    new_teacher_id = proposed.get('new_teacher_id')
                    
                    if not entry_id or not new_teacher_id:
                        raise Exception("Missing entry_id or new_teacher_id in proposal")
                        
                    ref_entry = ScheduleEntry.objects.get(id=entry_id)
                    new_teacher = Teacher.objects.get(teacher_id=new_teacher_id)
                    old_teacher_id = ref_entry.teacher_id
                    
                    # 1. Update EVERY ScheduleEntry for this course/section in this schedule
                    updated_entries = ScheduleEntry.objects.filter(
                        schedule_id=ref_entry.schedule_id,
                        course_id=ref_entry.course_id,
                        section_id=ref_entry.section_id
                    ).update(teacher=new_teacher)
                    
                    # 2. Update/Create TeacherCourseMapping for persistence
                    # First try to find a section-specific mapping
                    mapping_updated = TeacherCourseMapping.objects.filter(
                        course_id=ref_entry.course_id,
                        section_id=ref_entry.section_id
                    ).update(teacher=new_teacher)
                    
                    # If no section-specific mapping, check for a year-wide one if it was taught by the old teacher
                    if not mapping_updated:
                        # We don't want to update a year-wide mapping as it affects other sections
                        # Instead, we create a section-specific override for the new teacher
                        TeacherCourseMapping.objects.create(
                            teacher=new_teacher,
                            course_id=ref_entry.course_id,
                            section_id=ref_entry.section_id,
                            year=ref_entry.course.year, # Assuming course.year is available
                            preference_level=2
                        )
                        mapping_updated = "CREATED_OVERRIDE"

                    diag_info = f"[Bulk Swap] Updated {updated_entries} slots. Mapping: {mapping_updated}. Schedule: {ref_entry.schedule_id}"
                
                # Update Request Status
                change_request.status = 'APPROVED'
                change_request.reviewed_by = request.user
                change_request.reviewed_at = timezone.now()
                
                # Append diagnostic info if it's a swap
                original_notes = request.data.get('admin_notes', '')
                if change_request.change_type == 'SWAP':
                    change_request.admin_notes = f"{original_notes}\n{diag_info}".strip()
                else:
                    change_request.admin_notes = original_notes
                
                change_request.save()

            # Notify HOD
            Notification.objects.create(
                recipient=change_request.requested_by,
                title="Faculty Swap Approved",
                message=f"Swap approved for {change_request.proposed_data.get('course_id')} in {change_request.proposed_data.get('section_id')}. {change_request.admin_notes}"
            )
            
            serializer = self.get_serializer(change_request)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': f'Failed to apply changes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        except Exception as e:
            return Response(
                {'error': f'Failed to apply changes: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def reject(self, request, pk=None):
        """
        Reject a change request without applying changes.
        Admin only.
        """
        change_request = self.get_object()
        
        if change_request.status != 'PENDING':
            return Response(
                {'error': 'Only pending requests can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        change_request.status = 'REJECTED'
        change_request.reviewed_by = request.user
        change_request.reviewed_at = timezone.now()
        change_request.admin_notes = request.data.get('admin_notes', '')
        change_request.save()

        # Notify the requesting HOD
        Notification.objects.create(
            recipient=change_request.requested_by,
            title="Faculty Change Request Rejected",
            message=f"Your {change_request.change_type} request for {change_request.target_model} {change_request.target_id or '(New)'} has been rejected. {f'Notes: {change_request.admin_notes}' if change_request.admin_notes else ''}"
        )
        
        serializer = self.get_serializer(change_request)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for in-app notifications.
    Users can only see their own notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'marked as read'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all of the user's notifications as read."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).update(is_read=True)
        return Response({'status': 'all marked as read', 'count': count})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get the count of unread notifications for badge display."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({'count': count})
