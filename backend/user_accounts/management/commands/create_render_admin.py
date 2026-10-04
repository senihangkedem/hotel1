from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os


class Command(BaseCommand):
    help = "Create or update the Render admin user from environment variables"

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("RENDER_ADMIN_USERNAME")
        password = os.environ.get("RENDER_ADMIN_PASSWORD")
        email = os.environ.get("RENDER_ADMIN_EMAIL", "")

        if not username or not password:
            self.stdout.write(
                self.style.ERROR(
                    "RENDER_ADMIN_USERNAME and RENDER_ADMIN_PASSWORD are required."
                )
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "role": User.Role.OWNER,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        user.email = email
        user.role = User.Role.OWNER
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"Render admin user '{username}' {action} successfully."
            )
        )