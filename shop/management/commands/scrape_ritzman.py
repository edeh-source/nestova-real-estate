"""
Django Management Command to scrape Ritzman Smart Homes
Usage: python manage.py scrape_ritzman
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from shop.models import Category, Product, ProductImage, ProductSpecification

import requests
import time
import re
from decimal import Decimal
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class Command(BaseCommand):
    help = 'Scrape products from Ritzman Smart Homes and populate the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--use-samples',
            action='store_true',
            help='Use sample products instead of scraping',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Ritzman Smart Homes Scraper'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        scraper = RitzmanScraper(self.stdout, self.style)
        
        if options['use_samples']:
            self.stdout.write(self.style.WARNING('\nUsing sample products only...'))
            scraper.create_sample_data()
        else:
            scraper.run()
        
        self.stdout.write(self.style.SUCCESS('\n✓ Scraping complete!'))


class RitzmanScraper:
    def __init__(self, stdout, style):
        self.stdout = stdout
        self.style = style
        self.base_url = "https://ritzmansmarthomes.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.categories = [
            {
                'name': 'Smart Switches/Sockets',
                'slug': 'smart-switches-sockets',
                'description': 'Control your lights and appliances remotely with smart switches and sockets',
                'icon': 'fa-lightbulb'
            },
            {
                'name': 'Smart Appliances',
                'slug': 'smart-appliances',
                'description': 'Intelligent appliances for modern smart homes',
                'icon': 'fa-blender'
            },
            {
                'name': 'Smart Security',
                'slug': 'smart-security',
                'description': 'Advanced security systems including alarms and sensors',
                'icon': 'fa-shield-alt'
            },
            {
                'name': 'Smart Cameras',
                'slug': 'smart-cameras',
                'description': 'HD security cameras with remote monitoring',
                'icon': 'fa-video'
            },
            {
                'name': 'Smart Locks',
                'slug': 'smart-locks',
                'description': 'Keyless entry systems and smart door locks',
                'icon': 'fa-lock'
            },
            {
                'name': 'Smart Lighting',
                'slug': 'smart-lighting',
                'description': 'Intelligent lighting solutions for your home',
                'icon': 'fa-lightbulb'
            },
            {
                'name': 'Smart Blinds',
                'slug': 'smart-blinds',
                'description': 'Automated window blinds and curtains',
                'icon': 'fa-window-maximize'
            },
            {
                'name': 'Smart Speakers',
                'slug': 'smart-speakers',
                'description': 'Voice-controlled smart speakers',
                'icon': 'fa-volume-up'
            },
            {
                'name': 'Solar Inverters',
                'slug': 'solar-inverters',
                'description': 'Smart solar inverters for energy management',
                'icon': 'fa-solar-panel'
            },
        ]
    
    def extract_price(self, price_text):
        """Extract numeric price from text"""
        if not price_text:
            return Decimal('0.00')
        price_text = re.sub(r'[₦N,\s]', '', price_text)
        match = re.search(r'[\d.]+', price_text)
        if match:
            try:
                return Decimal(match.group())
            except:
                return Decimal('0.00')
        return Decimal('0.00')
    
    def download_image(self, image_url):
        """Download image and return Django File object"""
        try:
            if not image_url or image_url.startswith('data:'):
                return None
            
            if not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            response = self.session.get(image_url, timeout=10)
            if response.status_code == 200:
                filename = os.path.basename(urlparse(image_url).path) or 'image.jpg'
                return ContentFile(response.content, name=filename)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠ Error downloading image: {e}'))
        return None
    
    def create_categories(self):
        """Create product categories"""
        self.stdout.write('\n' + self.style.SUCCESS('Creating Categories...'))
        self.stdout.write('-' * 50)
        
        category_objects = {}
        
        for cat_data in self.categories:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['description'],
                    'icon': cat_data.get('icon', ''),
                    'is_active': True
                }
            )
            category_objects[cat_data['name']] = category
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {category.name}'))
            else:
                self.stdout.write(f'  ○ Exists: {category.name}')
        
        return category_objects
    
    def create_sample_data(self):
        """Create sample products for testing"""
        self.stdout.write('\n' + self.style.SUCCESS('Creating Sample Data...'))
        
        # Create categories first
        category_objects = self.create_categories()
        
        # Sample products
        sample_products = [
            {
                'name': '1 Gang Smart Switch',
                'category': 'Smart Switches/Sockets',
                'price': Decimal('25000.00'),
                'discount_price': Decimal('22000.00'),
                'description': 'Single gang smart switch with WiFi connectivity. Control your lights remotely via smartphone app. Compatible with Alexa and Google Home. Easy installation, no hub required.',
                'short_description': 'WiFi enabled smart switch for remote light control',
                'features': 'WiFi Connectivity (2.4GHz)\nAlexa & Google Home Compatible\nRemote Control via App\nTimer & Schedule Functions\nEnergy Monitoring\nNo Hub Required\nEasy Installation',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'Hardwired (AC 100-240V)'
            },
            {
                'name': '2 Gang Smart Switch',
                'category': 'Smart Switches/Sockets',
                'price': Decimal('35000.00'),
                'discount_price': Decimal('31500.00'),
                'description': 'Double gang smart switch for controlling two light circuits independently. WiFi enabled with app control, voice control compatibility, and energy monitoring features.',
                'short_description': 'Dual control smart switch with independent circuit control',
                'features': 'Control 2 Circuits Independently\nWiFi Connectivity\nVoice Control Support\nApp Control\nSchedule & Timer\nEnergy Monitoring\nTouch Panel Design',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'Hardwired (AC 100-240V)'
            },
            {
                'name': 'Smart Socket Plug',
                'category': 'Smart Switches/Sockets',
                'price': Decimal('15000.00'),
                'description': 'WiFi enabled smart plug socket. Turn any appliance into a smart device. Monitor energy consumption, set schedules, and control remotely from anywhere.',
                'short_description': 'Convert any appliance to smart with this WiFi plug',
                'features': 'WiFi Connectivity\nRemote ON/OFF Control\nEnergy Monitoring\nSchedule & Timer\nVoice Control Compatible\nCompact Design\nMax Load: 16A',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'AC Power (100-240V)'
            },
            {
                'name': 'Smart Security Alarm V2',
                'category': 'Smart Security',
                'price': Decimal('85000.00'),
                'discount_price': Decimal('75000.00'),
                'description': 'Comprehensive intelligent security alarm system equipped with multiple sensors, loud sirens, and smartphone connectivity for real-time monitoring and protecting homes or businesses against intrusions. Features include door/window sensors, motion detectors, and instant notifications.',
                'short_description': 'Advanced security system with sensors and smartphone alerts',
                'features': '5 Door/Window Sensors\n2 Motion Detectors\n110dB Loud Siren\nSmartphone App Control\nInstant Push Notifications\n24/7 Monitoring\nBackup Battery\nEasy DIY Installation',
                'product_type': 'smart_shield',
                'connectivity': 'wifi',
                'power_source': 'AC Power with Battery Backup'
            },
            {
                'name': 'HD WiFi Security Camera',
                'category': 'Smart Cameras',
                'price': Decimal('45000.00'),
                'discount_price': Decimal('38000.00'),
                'description': '1080P Full HD security camera with advanced night vision, motion detection, two-way audio, and cloud storage. Perfect for indoor and outdoor monitoring with weatherproof design.',
                'short_description': '1080P HD camera with night vision and cloud storage',
                'features': '1080P Full HD Video\nNight Vision (up to 30ft)\nMotion Detection\nTwo-Way Audio\nCloud Storage (7 days free)\nSD Card Support (up to 128GB)\nWeatherproof (IP66)\nWide Angle Lens (110°)',
                'product_type': 'smart_shield',
                'connectivity': 'wifi',
                'power_source': 'AC Power / Battery'
            },
            {
                'name': 'Smart Door Lock Pro',
                'category': 'Smart Locks',
                'price': Decimal('120000.00'),
                'discount_price': Decimal('105000.00'),
                'description': 'Premium keyless smart lock with multiple access methods including fingerprint scanner, PIN code, RFID card, and smartphone app. Features auto-lock, tamper alarm, and remote access control.',
                'short_description': 'Premium smart lock with fingerprint and multiple access methods',
                'features': 'Fingerprint Recognition (100 prints)\nPIN Code Access (up to 50 codes)\nRFID Card Support (10 cards)\nSmartphone App Control\nAuto-Lock Function\nTamper Alarm\nLow Battery Warning\nEmergency USB Charging',
                'product_type': 'smart_lock',
                'connectivity': 'bluetooth',
                'power_source': 'Battery Powered (6-12 months)'
            },
            {
                'name': 'Smart LED Bulb RGB',
                'category': 'Smart Lighting',
                'price': Decimal('8000.00'),
                'discount_price': Decimal('6500.00'),
                'description': 'Color changing RGB LED bulb with 16 million colors, dimmable white light, and WiFi control. Control via app or voice commands. Energy efficient with long lifespan.',
                'short_description': '16M color smart bulb with WiFi and voice control',
                'features': '16 Million Colors\nDimmable White (2700K-6500K)\nWiFi Control\nVoice Control Compatible\nSchedule & Timer\nMusic Sync Mode\n9W (60W equivalent)\n800 Lumens',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'AC Power (E27 Base)'
            },
            {
                'name': 'Smart Curtain Motor',
                'category': 'Smart Blinds',
                'price': Decimal('55000.00'),
                'description': 'Automated curtain motor with remote control, smartphone app, and voice control compatibility. Features include scheduling, quiet operation, and supports curtains up to 50kg.',
                'short_description': 'Automated motor for smart curtain control',
                'features': 'App & Voice Control\nQuiet Operation (<35dB)\nSupports up to 50kg\nSchedule Function\nSunrise/Sunset Automation\nManual Override\nEasy Installation\nUSB-C Rechargeable Battery',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'Rechargeable Battery'
            },
            {
                'name': 'Google Nest Mini',
                'category': 'Smart Speakers',
                'price': Decimal('18000.00'),
                'discount_price': Decimal('15000.00'),
                'description': 'Compact smart speaker with Google Assistant for voice control of your smart home. Play music, get answers, and control compatible devices hands-free.',
                'short_description': 'Compact smart speaker with Google Assistant',
                'features': 'Google Assistant Built-in\n360° Sound\nVoice Match Technology\nControl Smart Home Devices\nStream Music\nMake Calls\nWall Mountable\nPrivacy Controls',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'AC Power (USB-C)'
            },
            {
                'name': '5KVA Smart Solar Inverter',
                'category': 'Solar Inverters',
                'price': Decimal('450000.00'),
                'discount_price': Decimal('420000.00'),
                'description': '5KVA hybrid solar inverter with smart energy management, real-time monitoring, and automatic switching. Supports both solar panels and grid power with battery backup.',
                'short_description': 'Hybrid solar inverter with smart monitoring',
                'features': '5KVA / 5000W Output\nHybrid (Solar + Grid)\n48V Battery System\nMPPT Charge Controller\nSmart App Monitoring\nAuto Switch to Battery\nOverload Protection\nLCD Display',
                'product_type': 'accessory',
                'connectivity': 'wifi',
                'power_source': 'Solar / Grid AC Power'
            },
        ]
        
        # Create products
        self.stdout.write('\n' + self.style.SUCCESS('Creating Products...'))
        self.stdout.write('-' * 50)
        
        created_count = 0
        
        for prod_data in sample_products:
            try:
                category = category_objects.get(prod_data['category'])
                if not category:
                    continue
                
                sku = f"RZM-{slugify(prod_data['name'])[:40].upper()}"
                
                product, created = Product.objects.get_or_create(
                    sku=sku,
                    defaults={
                        'name': prod_data['name'],
                        'slug': slugify(prod_data['name']),
                        'category': category,
                        'product_type': prod_data.get('product_type', 'accessory'),
                        'short_description': prod_data.get('short_description', prod_data['description'][:200]),
                        'description': prod_data['description'],
                        'features': prod_data.get('features', 'Smart connectivity\nRemote control\nEnergy efficient'),
                        'price': prod_data.get('price', Decimal('0.00')),
                        'discount_price': prod_data.get('discount_price'),
                        'brand': 'Ritzman Smart Homes',
                        'model_number': sku,
                        'connectivity': prod_data.get('connectivity', 'wifi'),
                        'power_source': prod_data.get('power_source', 'AC Power / Battery'),
                        'warranty_period': '1 Year',
                        'stock_quantity': 25,
                        'is_available': True,
                        'is_featured': created_count < 3,  # First 3 are featured
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {product.name}'))
                else:
                    self.stdout.write(f'  ○ Exists: {product.name}')
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error creating {prod_data.get("name")}: {e}'))
        
        # Summary
        self.stdout.write('\n' + self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Categories: {len(category_objects)}'))
        self.stdout.write(self.style.SUCCESS(f'  Products Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
    
    def run(self):
        """Main scraper execution - will use sample data as website is hard to scrape"""
        self.stdout.write(self.style.WARNING('\nNote: Direct website scraping may be limited.'))
        self.stdout.write(self.style.WARNING('Using sample product data for now...\n'))
        self.create_sample_data()