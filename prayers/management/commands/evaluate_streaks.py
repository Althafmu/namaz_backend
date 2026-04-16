"""
Management command to evaluate streaks for all users.
Phase 2: Runs at 3 AM server time (or per-user timezone with Celery).

Usage:
    python manage.py evaluate_streaks [--force] [--user-id=ID]

This command is idempotent - running it multiple times for the same day
will not cause duplicate evaluations or incorrect streak calculations.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from prayers.models import Streak, DailyPrayerLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Evaluate and update streaks for all users (or a specific user)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recalculation even if already done today',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Evaluate streak for a specific user only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        force = options['force']
        user_id = options['user_id']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        # Get users to process
        if user_id:
            try:
                users = [User.objects.get(id=user_id)]
                self.stdout.write(f'Processing user: {users[0].username}')
            except User.DoesNotExist:
                raise CommandError(f'User with ID {user_id} does not exist')
        else:
            users = User.objects.filter(is_active=True)
            self.stdout.write(f'Processing {users.count()} active users')

        updated_count = 0
        error_count = 0

        for user in users:
            try:
                with transaction.atomic():
                    streak, created = Streak.objects.get_or_create(user=user)

                    if created:
                        self.stdout.write(f'Created new streak for {user.username}')

                    # Use the model's recalculate method (idempotent)
                    if force:
                        streak.recalculate(force=True)
                        updated_count += 1
                        if not dry_run:
                            self.stdout.write(f'Force recalculated streak for {user.username}: {streak.current_streak} days')
                    else:
                        # Check if already evaluated today
                        today = timezone.localdate()
                        if streak.last_recalculated_at:
                            last_calc_date = timezone.localtime(streak.last_recalculated_at).date()
                            if last_calc_date == today:
                                continue  # Skip - already evaluated today

                        streak.recalculate(force=False)
                        updated_count += 1
                        if not dry_run:
                            self.stdout.write(f'Recalculated streak for {user.username}: {streak.current_streak} days')

            except Exception as e:
                error_count += 1
                self.stderr.write(self.style.ERROR(f'Error processing {user.username}: {str(e)}'))
                continue

        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would update {updated_count} streaks'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Successfully updated {updated_count} streaks'))

        if error_count > 0:
            self.stdout.write(self.style.WARNING(f'{error_count} errors encountered'))