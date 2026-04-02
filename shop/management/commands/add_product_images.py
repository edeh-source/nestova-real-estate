"""
Add Stock Images to Products
This will download placeholder images for products that don't have images yet
Usage: python manage.py add_product_images
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from shop.models import Product, ProductImage
import requests


class Command(BaseCommand):
    help = 'Add placeholder images to products without images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download images even if products already have them',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Adding Images to Products'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        force = options.get('force', False)
        
        # Get products without images
        if force:
            products = Product.objects.all()
            self.stdout.write(f'\nForce mode: Processing all {products.count()} products')
        else:
            products = Product.objects.filter(main_image='')
            self.stdout.write(f'\nFound {products.count()} products without images')
        
        if not products.exists():
            self.stdout.write(self.style.SUCCESS('\n✓ All products already have images!'))
            return
        
        updated = 0
        
        for product in products:
            self.stdout.write(f'\n  Processing: {product.name}')
            
            # Determine image query based on product type
            query = self.get_image_query(product)
            
            # Download placeholder image
            image_url = f"https://source.unsplash.com/800x600/?{query}"
            
            try:
                self.stdout.write(f'    Downloading from Unsplash...')
                response = requests.get(image_url, timeout=10)
                
                if response.status_code == 200:
                    filename = f"{product.slug[:50]}.jpg"
                    image_file = ContentFile(response.content, name=filename)
                    
                    product.main_image = image_file
                    product.save()
                    
                    updated += 1
                    self.stdout.write(self.style.SUCCESS(f'    ✓ Image added'))
                else:
                    self.stdout.write(self.style.WARNING(f'    ⚠ Failed: HTTP {response.status_code}'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error: {e}'))
        
        self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS(f'✓ Complete! Updated {updated} products'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
    
    def get_image_query(self, product):
        """Generate appropriate image search query"""
        name = product.name.lower()
        category = product.category.name.lower()
        
        # Map to good Unsplash search terms
        if 'switch' in name or 'socket' in name:
            return 'light,switch,smart,home'
        elif 'camera' in name or 'camera' in category:
            return 'security,camera,surveillance'
        elif 'lock' in name or 'lock' in category:
            return 'door,lock,security,smart'
        elif 'alarm' in name or 'security' in name:
            return 'alarm,security,system'
        elif 'bulb' in name or 'light' in name or 'lighting' in category:
            return 'led,bulb,light,smart'
        elif 'blind' in name or 'curtain' in name:
            return 'curtain,blind,window'
        elif 'speaker' in name or 'speaker' in category:
            return 'speaker,smart,google,alexa'
        elif 'solar' in name or 'inverter' in name:
            return 'solar,panel,energy,inverter'
        else:
            return 'smart,home,technology,iot'