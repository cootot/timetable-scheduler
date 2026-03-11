"""
Database Backup Management Command

Creates a timestamped copy of the SQLite database.
Usage: python manage.py backup_db

Author: System Team
Story: 6.2 - Automated Backups
"""

import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Create a timestamped backup of the SQLite database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-backups',
            type=int,
            default=30,
            help='Maximum number of backups to keep (default: 30)',
        )

    def handle(self, *args, **options):
        max_backups = options['max_backups']

        db_path = settings.DATABASES['default']['NAME']
        engine = settings.DATABASES['default']['ENGINE']
        is_sqlite = 'sqlite' in engine

        # Create backups directory next to the database
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        
        if is_sqlite:
            if not os.path.exists(db_path):
                self.stderr.write(self.style.ERROR(f'Database not found: {db_path}'))
                return
            backup_filename = f'db_{timestamp}.sqlite3'
            backup_path = os.path.join(backup_dir, backup_filename)
            try:
                shutil.copy2(str(db_path), backup_path)
                file_size = os.path.getsize(backup_path)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Backup created: {backup_filename} ({file_size:,} bytes)'
                    )
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Backup failed: {e}'))
                return
        else:
            backup_filename = f'db_{timestamp}.json'
            backup_path = os.path.join(backup_dir, backup_filename)
            from django.core.management import call_command
            try:
                # Use explicit UTF-8 encoding to avoid Windows default encoding issues
                with open(backup_path, 'w', encoding='utf-8') as f:
                    call_command('dumpdata', format='json', indent=2, stdout=f,
                                 exclude=['auth.permission', 'contenttypes.contenttype'])
                file_size = os.path.getsize(backup_path)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Backup created: {backup_filename} ({file_size:,} bytes)'
                    )
                )
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Backup failed: {e}'))
                return

        # Cleanup old backups (keep only max_backups most recent)
        backups = sorted([
            f for f in os.listdir(backup_dir)
            if f.startswith('db_') and f.endswith('.sqlite3')
        ])

        if len(backups) > max_backups:
            to_delete = backups[:len(backups) - max_backups]
            for old_backup in to_delete:
                old_path = os.path.join(backup_dir, old_backup)
                os.remove(old_path)
                self.stdout.write(
                    self.style.WARNING(f'Deleted old backup: {old_backup}')
                )

        remaining = len([
            f for f in os.listdir(backup_dir)
            if f.startswith('db_') and f.endswith('.sqlite3')
        ])
        self.stdout.write(f'Total backups: {remaining}/{max_backups}')
