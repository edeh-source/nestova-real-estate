"""
Add Images to Products - Enhanced with Multiple Sources
Usage: python manage.py add_images
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from shop.models import Product, ProductImage
import requests
import time


class Command(BaseCommand):
    help = 'Add images to products using multiple sources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download images even if products already have them',
        )
        parser.add_argument(
            '--source',
            type=str,
            default='all',
            choices=['unsplash', 'picsum', 'placeholder', 'all'],
            help='Image source to use',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Adding Images to Products'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        force = options.get('force', False)
        source = options.get('source', 'all')
        
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
        failed = 0
        
        for i, product in enumerate(products, 1):
            self.stdout.write(f'\n[{i}/{products.count()}] Processing: {product.name}')
            
            # Try multiple sources
            image_downloaded = False
            
            if source == 'all' or source == 'picsum':
                if self.download_picsum_image(product):
                    updated += 1
                    image_downloaded = True
                    time.sleep(0.5)  # Be nice to the API
                    continue
            
            if source == 'all' or source == 'unsplash':
                if self.download_unsplash_image(product):
                    updated += 1
                    image_downloaded = True
                    time.sleep(1)
                    continue
            
            if source == 'all' or source == 'placeholder':
                if self.download_placeholder_image(product):
                    updated += 1
                    image_downloaded = True
                    continue
            
            if not image_downloaded:
                failed += 1
                self.stdout.write(self.style.ERROR('    ✗ All sources failed'))
        
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  ✓ Images added: {updated}'))
        if failed > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠ Failed: {failed}'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
    
    def download_picsum_image(self, product):
        """Download from Lorem Picsum (no rate limits)"""
        try:
            self.stdout.write('    Trying Picsum...')
            
            # Picsum provides random images with specific dimensions
            # We'll use a seed based on product ID for consistency
            seed = abs(hash(str(product.id))) % 1000
            url = f"https://picsum.photos/seed/{seed}/800/600"
            
            response = requests.get(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                filename = f"{product.slug[:50]}.jpg"
                image_file = ContentFile(response.content, name=filename)
                
                product.main_image = image_file
                product.save()
                
                self.stdout.write(self.style.SUCCESS('    ✓ Image added from Picsum'))
                return True
            else:
                self.stdout.write(self.style.WARNING(f'    ⚠ Picsum failed: HTTP {response.status_code}'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ⚠ Picsum error: {str(e)[:50]}'))
        
        return False
    
    def download_unsplash_image(self, product):
        """Download from Unsplash"""
        try:
            self.stdout.write('    Trying Unsplash...')
            
            query = self.get_image_query(product)
            url = f"https://source.unsplash.com/800x600/?{query}"
            
            response = requests.get(url, timeout=15, allow_redirects=True)
            
            if response.status_code == 200:
                filename = f"{product.slug[:50]}.jpg"
                image_file = ContentFile(response.content, name=filename)
                
                product.main_image = image_file
                product.save()
                
                self.stdout.write(self.style.SUCCESS('    ✓ Image added from Unsplash'))
                return True
            else:
                self.stdout.write(self.style.WARNING(f'    ⚠ Unsplash failed: HTTP {response.status_code}'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ⚠ Unsplash error: {str(e)[:50]}'))
        
        return False
    
    def download_placeholder_image(self, product):
        """Download from Placeholder.com"""
        try:
            self.stdout.write('    Trying Placeholder.com...')
            
            # Create a colored placeholder with text
            color = self.get_color_for_category(product.category.name)
            text = product.name[:20]
            
            url = f"https://via.placeholder.com/800x600/{color}/ffffff?text={text}"
            
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                filename = f"{product.slug[:50]}.png"
                image_file = ContentFile(response.content, name=filename)
                
                product.main_image = image_file
                product.save()
                
                self.stdout.write(self.style.SUCCESS('    ✓ Placeholder image added'))
                return True
            else:
                self.stdout.write(self.style.WARNING(f'    ⚠ Placeholder failed: HTTP {response.status_code}'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'    ⚠ Placeholder error: {str(e)[:50]}'))
        
        return False
    
    def get_image_query(self, product):
        """Generate appropriate image search query"""
        name = product.name.lower()
        category = product.category.name.lower()
        
        # Map to good search terms
        if 'switch' in name or 'socket' in name:
            return 'light-switch,smart-home'
        elif 'camera' in name or 'camera' in category:
            return 'security-camera,surveillance'
        elif 'lock' in name or 'lock' in category:
            return 'door-lock,smart-lock'
        elif 'alarm' in name or 'security' in name:
            return 'alarm-system,security'
        elif 'bulb' in name or 'light' in name or 'lighting' in category:
            return 'led-bulb,smart-lighting'
        elif 'blind' in name or 'curtain' in name:
            return 'window-blinds,curtain'
        elif 'speaker' in name or 'speaker' in category:
            return 'smart-speaker,voice-assistant'
        elif 'solar' in name or 'inverter' in name:
            return 'solar-panel,inverter'
        else:
            return 'smart-home,iot-device'
    
    def get_color_for_category(self, category_name):
        """Get color code for category"""
        colors = {
            'smart switches': '4A90E2',
            'smart security': 'E74C3C',
            'smart cameras': '9B59B6',
            'smart locks': '2ECC71',
            'smart lighting': 'F39C12',
            'smart blinds': '1ABC9C',
            'smart speakers': '3498DB',
            'solar inverters': 'E67E22',
            'smart appliances': '95A5A6',
        }
        
        category_lower = category_name.lower()
        for key, color in colors.items():
            if key in category_lower:
                return color
        
        return '7F8C8D'  # Default gray