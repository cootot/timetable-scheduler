"""
System Health & Backup API Views

Provides endpoints for database backup management.
Admin-only access.

Author: System Team
Story: 6.2 - Automated Backups
"""

import os
import json
import shutil
from datetime import datetime

from django.conf import settings
from django.core.management import call_command
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsAdmin
from core.models import AuditLog


BACKUP_DIR = os.path.join(settings.BASE_DIR, 'backups')


@api_view(['GET'])
@permission_classes([IsAdmin])
def list_backups(request):
    """
    List all available database backups.
    GET /api/system/backups/
    """
    if not os.path.exists(BACKUP_DIR):
        return Response({'backups': [], 'count': 0})

    # Load metadata (labels)
    metadata = _load_metadata()

    backups = []
    for filename in os.listdir(BACKUP_DIR):
        if filename.startswith('db_') and (filename.endswith('.sqlite3') or filename.endswith('.json')):
            filepath = os.path.join(BACKUP_DIR, filename)
            stat = os.stat(filepath)
            
            # Parse timestamp from filename: db_YYYY-MM-DD_HHMMSS.extension or db_pre_restore_YYYY...
            created_iso = None
            timestamp_obj = datetime.min # Default for sorting if parsing fails

            try:
                date_str = filename.replace('.sqlite3', '').replace('.json', '')
                if date_str.startswith('db_pre_restore_'):
                    date_str = date_str.replace('db_pre_restore_', '')
                elif date_str.startswith('db_'):
                    date_str = date_str.replace('db_', '')
                
                created = datetime.strptime(date_str, '%Y-%m-%d_%H%M%S')
                created_iso = created.isoformat()
                timestamp_obj = created
            except ValueError:
                pass

            backups.append({
                'filename': filename,
                'label': metadata.get(filename, {}).get('label', ''),
                'size_bytes': stat.st_size,
                'size_display': _format_size(stat.st_size),
                'created_at': created_iso,
                '_sort_key': timestamp_obj, # temporary key for sorting
            })

    # Sort by timestamp descending (newest first)
    backups.sort(key=lambda x: x['_sort_key'], reverse=True)

    # Remove the temporary sort key
    for b in backups:
        del b['_sort_key']

    return Response({
        'backups': backups,
        'count': len(backups),
    })


@api_view(['POST'])
@permission_classes([IsAdmin])
def create_backup(request):
    """
    Create a new database backup immediately.
    POST /api/system/backups/create/
    Body (optional): {"label": "before semester reset"}
    """
    label = request.data.get('label', '').strip() if request.data else ''

    try:
        # Use common helper for backup
        backup_info = _create_db_backup(label)
        
        # Log to audit trail
        AuditLog.objects.create(
            user_name=request.user.username if request.user.is_authenticated else 'System',
            action='BACKUP',
            model_name='Database',
            object_id=backup_info['filename'],
            details={'label': label, 'size': backup_info['size_display']},
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response(backup_info, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
            {'error': f'Backup failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAdmin])
def reset_semester(request):
    """
    Archive current data and reset for new semester.
    POST /api/system/reset-semester/
    Body: {"confirmation": "CONFIRM"}
    
    Preserves: Teachers, Courses, Rooms, Sections, Users.
    Deletes: Schedules, Mappings, Conflicts, ChangeRequests.
    """
    confirmation = request.data.get('confirmation', '')
    if confirmation != 'CONFIRM':
        return Response(
            {'error': 'Safety lock active. You must type "CONFIRM" to proceed.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # 1. Create Archive Backup
        backup_info = _create_db_backup("Pre-Rollover Archive")
        
        # 2. Perform Reset
        from django.db import transaction
        from core.models import Schedule, TeacherCourseMapping, ConflictLog, ChangeRequest
        
        with transaction.atomic():
            # Delete operational data
            schedule_count, _ = Schedule.objects.all().delete()
            mapping_count, _ = TeacherCourseMapping.objects.all().delete()
            conflict_count, _ = ConflictLog.objects.all().delete()
            request_count, _ = ChangeRequest.objects.all().delete()
            
            # Log the reset
            AuditLog.objects.create(
                user_name=request.user.username if request.user.is_authenticated else 'System',
                action='UPDATE', # Using UPDATE as we are modifying system state significantly
                model_name='System',
                object_id='SEMESTER_RESET',
                details={
                    'backup': backup_info['filename'],
                    'deleted': {
                        'schedules': schedule_count,
                        'mappings': mapping_count,
                        'conflicts': conflict_count,
                        'requests': request_count
                    }
                },
                ip_address=request.META.get('REMOTE_ADDR'),
            )

        return Response({
            'message': 'Semester reset successful.',
            'backup': backup_info['filename'],
            'stats': {
                'schedules_deleted': schedule_count,
                'mappings_deleted': mapping_count,
            }
        })

    except Exception as e:
        return Response(
            {'error': f'Reset failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _create_db_backup(label):
    """Helper to create a database backup and return its info dict."""
    call_command('backup_db')

    if os.path.exists(BACKUP_DIR):
        files = sorted([
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith('db_') and (f.endswith('.sqlite3') or f.endswith('.json'))
        ])
        if files:
            latest = files[-1]
            filepath = os.path.join(BACKUP_DIR, latest)

            # Save label in metadata
            if label:
                metadata = _load_metadata()
                metadata[latest] = {'label': label}
                _save_metadata(metadata)
            
            return {
                'message': f'Backup created: {latest}',
                'filename': latest,
                'label': label,
                'size_bytes': os.path.getsize(filepath),
                'size_display': _format_size(os.path.getsize(filepath)),
            }
            
    raise Exception('Backup command ran but no file was created')


@api_view(['POST'])
@permission_classes([IsAdmin])
def restore_backup(request, filename):
    """
    Restore the database from a backup file.
    POST /api/system/restore/<filename>/

    WARNING: This replaces the current database!
    """
    # Validate the filename to prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return Response(
            {'error': 'Invalid filename'},
            status=status.HTTP_400_BAD_REQUEST
        )

    backup_path = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(backup_path):
        return Response(
            {'error': f'Backup file not found: {filename}'},
            status=status.HTTP_404_NOT_FOUND
        )

    db_path = str(settings.DATABASES['default']['NAME'])
    engine = settings.DATABASES['default']['ENGINE']

    try:
        # Create a safety backup of the CURRENT state before restoring
        safety_dir = os.path.join(BACKUP_DIR)
        os.makedirs(safety_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        is_sqlite = 'sqlite' in engine

        if is_sqlite:
            safety_name = f'db_pre_restore_{timestamp}.sqlite3'
            safety_path = os.path.join(safety_dir, safety_name)
            shutil.copy2(db_path, safety_path)
            
            if filename.endswith('.sqlite3'):
                shutil.copy2(backup_path, db_path)
            elif filename.endswith('.json'):
                call_command('flush', '--noinput')
                call_command('loaddata', backup_path)
            else:
                return Response({'error': 'Unsupported backup format.'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            safety_name = f'db_pre_restore_{timestamp}.json'
            safety_path = os.path.join(safety_dir, safety_name)
            # Use explicit UTF-8 encoding to avoid Windows default encoding issues
            with open(safety_path, 'w', encoding='utf-8') as f:
                call_command('dumpdata', format='json', indent=2, stdout=f, 
                             exclude=['auth.permission', 'contenttypes.contenttype'])
            
            if filename.endswith('.json'):
                call_command('flush', '--noinput')
                call_command('loaddata', backup_path)
            else:
                return Response(
                    {'error': 'Cannot restore an SQLite backup (.sqlite3) directly into a PostgreSQL database. Please use a JSON backup.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Log to audit trail (this goes to audit_db, which is NOT restored)
        AuditLog.objects.create(
            user_name=request.user.username if request.user.is_authenticated else 'System',
            action='RESTORE',
            model_name='Database',
            object_id=filename,
            details={'safety_backup': safety_name, 'restored_from': filename},
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response({
            'message': f'Database restored from {filename}',
            'safety_backup': safety_name,
            'restored_from': filename,
        })

    except Exception as e:
        return Response(
            {'error': f'Restore failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAdmin])
def delete_backup(request, filename):
    """
    Delete a specific backup file.
    DELETE /api/system/backups/<filename>/
    """
    if '..' in filename or '/' in filename or '\\' in filename:
        return Response(
            {'error': 'Invalid filename'},
            status=status.HTTP_400_BAD_REQUEST
        )

    backup_path = os.path.join(BACKUP_DIR, filename)

    if not os.path.exists(backup_path):
        return Response(
            {'error': f'Backup file not found: {filename}'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        # Also remove from metadata
        metadata = _load_metadata()
        metadata.pop(filename, None)
        _save_metadata(metadata)

        os.remove(backup_path)
        return Response({'message': f'Deleted: {filename}'})
    except Exception as e:
        return Response(
            {'error': f'Delete failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdmin])
def system_info(request):
    """
    Get system health information.
    GET /api/system/info/
    """
    db_path = str(settings.DATABASES['default']['NAME'])
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    backup_count = 0
    total_backup_size = 0
    if os.path.exists(BACKUP_DIR):
        backup_files = [
            f for f in os.listdir(BACKUP_DIR)
            if f.startswith('db_') and (f.endswith('.sqlite3') or f.endswith('.json'))
        ]
        backup_count = len(backup_files)
        total_backup_size = sum(
            os.path.getsize(os.path.join(BACKUP_DIR, f))
            for f in backup_files
        )

    return Response({
        'database': {
            'engine': 'SQLite',
            'size_bytes': db_size,
            'size_display': _format_size(db_size),
            'path': os.path.basename(db_path),
        },
        'backups': {
            'count': backup_count,
            'total_size_bytes': total_backup_size,
            'total_size_display': _format_size(total_backup_size),
            'directory': 'backups/',
        },
    })


def _format_size(size_bytes):
    """Format bytes into human-readable size."""
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    else:
        return f'{size_bytes / (1024 * 1024 * 1024):.1f} GB'


def _load_metadata():
    """Load backup metadata (labels) from JSON file."""
    meta_path = os.path.join(BACKUP_DIR, 'metadata.json')
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_metadata(metadata):
    """Save backup metadata (labels) to JSON file."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    meta_path = os.path.join(BACKUP_DIR, 'metadata.json')
    with open(meta_path, 'w') as f:
        json.dump(metadata, f, indent=2)
