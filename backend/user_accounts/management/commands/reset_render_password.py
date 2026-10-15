import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reset an existing user's password using a temporary environment variable."

    def handle(self, *args, **options):
        username = os.environ.get("RESET_ADMIN_USERNAME", "bob")
        password = os.environ.get("RENDER_ADMIN_PASSWORD", "")
        if not password:
            raise CommandError("RENDER_ADMIN_PASSWORD is not configured.")

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"User '{username}' does not exist.")

        user.set_password(password)
        user.save(update_fields=["password"])
        self.stdout.write(
            self.style.SUCCESS(f"Password reset successfully for '{username}'.")
        )
