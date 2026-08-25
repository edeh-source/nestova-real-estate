from django.core.management.base import BaseCommand
from django.utils import timezone
from listings.models import UserSubscription


class Command(BaseCommand):
    help = "Scan all active user subscriptions and perform auto-boost on listings whose scheduled boost is due."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force run auto-boost on all active subscribers regardless of schedule.',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        now = timezone.now()

        self.stdout.write(self.style.MIGRATE_HEADING("=== Running Auto-Boost Processor ==="))
        self.stdout.write(f"Current server time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        active_subs = UserSubscription.objects.filter(is_active=True).select_related('package', 'user')

        boosted_users = 0
        total_properties_boosted = 0

        for sub in active_subs:
            if not sub.package or sub.is_expired:
                continue

            # Free package has no auto-boost
            if sub.package.slug == 'freemium' or sub.package.price == 0:
                continue

            if force or sub.needs_auto_boost():
                count = sub.perform_auto_boost()
                boosted_users += 1
                total_properties_boosted += count
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[BOOSTED] {count} listings for {sub.user.username} (Plan: {sub.package.name}, Next: {sub.next_auto_boost_at.strftime('%Y-%m-%d %H:%M')})"
                    )
                )

        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Auto-boost cycle completed: Boosted {total_properties_boosted} listings across {boosted_users} users."
        ))
