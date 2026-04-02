from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
import os

class Command(BaseCommand):
    help = 'Setup Google OAuth app for production'

    def handle(self, *args, **options):
        # Get environment variables
        client_id = os.environ.get('CLIENT_ID')
        client_secret = os.environ.get('CLIENT_SECRET')
        
        if not client_id or not client_secret:
            self.stdout.write(self.style.ERROR(
                '❌ CLIENT_ID and CLIENT_SECRET environment variables are required!'
            ))
            self.stdout.write('Please set them in your Render environment variables.')
            return
        
        # Get current site
        try:
            site = Site.objects.get_current()
            self.stdout.write(f'Current site: {site.domain}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Using default site'))
            site = Site.objects.get(pk=1)
        
        # Check for existing Google apps
        google_apps = SocialApp.objects.filter(provider='google')
        
        if google_apps.count() > 1:
            self.stdout.write(self.style.WARNING(
                f'Found {google_apps.count()} Google apps. Removing duplicates...'
            ))
            # Keep first, delete rest
            first_app = google_apps.first()
            google_apps.exclude(id=first_app.id).delete()
            google_app = first_app
            self.stdout.write(self.style.SUCCESS('✓ Removed duplicate Google apps'))
        elif google_apps.count() == 1:
            google_app = google_apps.first()
            self.stdout.write('Found existing Google OAuth app')
        else:
            # Create new Google app
            google_app = SocialApp.objects.create(
                provider='google',
                name='Google',
                client_id=client_id,
                secret=client_secret,
            )
            self.stdout.write(self.style.SUCCESS('✓ Created Google OAuth app'))
        
        # Update credentials
        google_app.client_id = client_id
        google_app.secret = client_secret
        google_app.save()
        self.stdout.write(self.style.SUCCESS('✓ Updated Google OAuth credentials'))
        
        # Clear and set site association
        google_app.sites.clear()
        google_app.sites.add(site)
        self.stdout.write(self.style.SUCCESS(f'✓ Associated with site: {site.domain}'))
        
        self.stdout.write(self.style.SUCCESS(
            '\n✅ Google OAuth setup complete!'
        ))
        self.stdout.write(f'   Provider: {google_app.provider}')
        self.stdout.write(f'   Client ID: {google_app.client_id[:20]}...')
        self.stdout.write(f'   Site: {site.domain}')
