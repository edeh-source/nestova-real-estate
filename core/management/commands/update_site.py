from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
import os

class Command(BaseCommand):
    help = 'Update Django site to production domain'

    def handle(self, *args, **options):
        # Determine the correct domain
        debug = os.environ.get('DEBUG', 'False') == 'True'
        
        if debug:
            domain = 'localhost:8000'
            name = 'Nestova Local'
        else:
            domain = 'nestovaproperty.com'
            name = 'Nestova'
        
        # Update or create site
        try:
            site = Site.objects.get(pk=1)
            old_domain = site.domain
            site.domain = domain
            site.name = name
            site.save()
            
            self.stdout.write(self.style.SUCCESS(
                f'✓ Updated site: {old_domain} → {domain}'
            ))
        except Site.DoesNotExist:
            site = Site.objects.create(
                pk=1,
                domain=domain,
                name=name
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ Created site: {domain}'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Site configuration complete!'
        ))
        self.stdout.write(f'   Domain: {site.domain}')
        self.stdout.write(f'   Name: {site.name}')
