from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp

class Command(BaseCommand):
    help = 'Fix duplicate Google OAuth app entries'

    def handle(self, *args, **options):
        # Find all Google apps
        google_apps = SocialApp.objects.filter(provider='google')
        count = google_apps.count()
        
        self.stdout.write(f'Found {count} Google OAuth app(s)')
        
        if count == 0:
            self.stdout.write(self.style.WARNING('No Google apps found. Please add one in Django admin.'))
            return
        
        if count == 1:
            self.stdout.write(self.style.SUCCESS('✓ Only one Google app exists. No duplicates to remove.'))
            return
        
        # Show all apps
        self.stdout.write('\nCurrent Google apps:')
        for app in google_apps:
            self.stdout.write(f'  ID: {app.id}, Name: {app.name}, Client ID: {app.client_id[:30]}...')
        
        # Keep the first one, delete the rest
        first_app = google_apps.first()
        duplicates = google_apps.exclude(id=first_app.id)
        duplicate_count = duplicates.count()
        
        self.stdout.write(f'\nKeeping: ID {first_app.id} - {first_app.name}')
        self.stdout.write(f'Deleting {duplicate_count} duplicate(s)...')
        
        duplicates.delete()
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully removed {duplicate_count} duplicate Google app(s)!'))
        self.stdout.write(self.style.SUCCESS(f'✓ Remaining Google apps: {SocialApp.objects.filter(provider="google").count()}'))
