from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates an initial admin user or updates an existing one with the correct role'

    def handle(self, *args, **options):
        User = get_user_model()
        username = 'admin'
        email = 'admin@example.com'
        password = 'admin123'
        
        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        
        # Always enforce these critical fields for the admin user
        user.set_password(password)
        user.role = 'ADMIN'
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"Successfully created new admin user '{username}' with role 'ADMIN'"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Successfully updated existing user '{username}' to have role 'ADMIN'"))
