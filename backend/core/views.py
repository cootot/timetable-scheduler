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
from django.utils import timezone
from .models import (
    Teacher, Course, Room, TimeSlot, Section,
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


class TeacherCourseMappingViewSet(viewsets.ModelViewSet):
    """
    API endpoint for TeacherCourseMapping CRUD operations.
    """
    queryset = TeacherCourseMapping.objects.all()
    serializer_class = TeacherCourseMappingSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [IsHODOrAdmin]
        return [permission() for permission in permission_classes]


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
        """Automatically set requested_by to current user"""
        serializer.save(requested_by=self.request.user)
    
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
        
        try:
            # Apply the change based on type
            if change_request.target_model == 'Teacher':
                if change_request.change_type == 'CREATE':
                    # Create new teacher
                    Teacher.objects.create(**change_request.proposed_data)
                
                elif change_request.change_type == 'UPDATE':
                    # Update existing teacher
                    teacher = Teacher.objects.get(teacher_id=change_request.target_id)
                    for key, value in change_request.proposed_data.items():
                        setattr(teacher, key, value)
                    teacher.save()
                
                elif change_request.change_type == 'DELETE':
                    # Delete teacher
                    teacher = Teacher.objects.get(teacher_id=change_request.target_id)
                    teacher.delete()
            
            # Update request status
            change_request.status = 'APPROVED'
            change_request.reviewed_by = request.user
            change_request.reviewed_at = timezone.now()
            change_request.admin_notes = request.data.get('admin_notes', '')
            change_request.save()
            
            serializer = self.get_serializer(change_request)
            return Response(serializer.data)
        
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
