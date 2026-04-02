from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

class Command(BaseCommand):
    help = 'Fix Google OAuth app site association'

    def handle(self, *args, **options):
        # Get the current site
        try:
            site = Site.objects.get_current()
            self.stdout.write(f'Current site: {site.domain} (ID: {site.id})')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting current site: {e}'))
            return
        
        # Get all sites
        all_sites = Site.objects.all()
        self.stdout.write(f'\nAll sites in database:')
        for s in all_sites:
            self.stdout.write(f'  ID: {s.id}, Domain: {s.domain}, Name: {s.name}')
        
        # Get Google app
        google_apps = SocialApp.objects.filter(provider='google')
        
        if google_apps.count() == 0:
            self.stdout.write(self.style.WARNING('\nNo Google OAuth app found!'))
            return
        
        google_app = google_apps.first()
        self.stdout.write(f'\nGoogle OAuth app: {google_app.name}')
        
        # Check current site associations
        current_sites = google_app.sites.all()
        self.stdout.write(f'Currently associated with {current_sites.count()} site(s):')
        for s in current_sites:
            self.stdout.write(f'  - {s.domain} (ID: {s.id})')
        
        # Clear all site associations
        google_app.sites.clear()
        self.stdout.write(self.style.WARNING('\nCleared all site associations'))
        
        # Associate with current site only
        google_app.sites.add(site)
        self.stdout.write(self.style.SUCCESS(f'✓ Associated Google app with site: {site.domain}'))
        
        # Verify
        final_sites = google_app.sites.all()
        self.stdout.write(f'\nFinal site associations ({final_sites.count()}):')
        for s in final_sites:
            self.stdout.write(f'  - {s.domain} (ID: {s.id})')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Google OAuth app site association fixed!'))
