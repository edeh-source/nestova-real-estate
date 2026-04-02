"""
Enhanced Ritzman Scraper with Real Web Crawling and Image Download
Usage: python manage.py scrape_ritzman_full
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from shop.models import Category, Product, ProductImage, ProductSpecification

import requests
import time
import re
import os
from decimal import Decimal
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class Command(BaseCommand):
    help = 'Scrape Ritzman Smart Homes with images'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            type=str,
            help='Scrape specific category only',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Max products per category',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Ritzman Smart Homes - Full Web Scraper with Images'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        scraper = RitzmanFullScraper(self.stdout, self.style)
        scraper.run(
            specific_category=options.get('category'),
            limit=options.get('limit', 100)
        )
        
        self.stdout.write(self.style.SUCCESS('\n✓ Scraping complete!'))


class RitzmanFullScraper:
    def __init__(self, stdout, style):
        self.stdout = stdout
        self.style = style
        self.base_url = "https://ritzmansmarthomes.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        
        self.categories_scraped = []
        self.products_scraped = []
    
    def extract_price(self, price_text):
        """Extract numeric price from text"""
        if not price_text:
            return None
        price_text = re.sub(r'[₦N,\s]', '', price_text)
        match = re.search(r'[\d.]+', price_text)
        if match:
            try:
                return Decimal(match.group())
            except:
                return None
        return None
    
    def download_image(self, image_url, product_name):
        """Download image and return Django File object"""
        try:
            if not image_url or image_url.startswith('data:'):
                return None
            
            # Make absolute URL
            if not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            self.stdout.write(f'      Downloading: {image_url[:60]}...')
            
            response = self.session.get(image_url, timeout=15)
            if response.status_code == 200:
                # Get filename
                filename = os.path.basename(urlparse(image_url).path)
                if not filename or len(filename) < 3:
                    filename = f"{slugify(product_name)[:30]}.jpg"
                
                # Ensure it has an extension
                if '.' not in filename:
                    filename += '.jpg'
                
                self.stdout.write(self.style.SUCCESS(f'      ✓ Downloaded: {filename}'))
                return ContentFile(response.content, name=filename)
            else:
                self.stdout.write(self.style.WARNING(f'      ⚠ Failed: HTTP {response.status_code}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'      ⚠ Error: {str(e)[:50]}'))
        return None
    
    def fetch_page(self, url, retries=3):
        """Fetch page with retries"""
        for attempt in range(retries):
            try:
                self.stdout.write(f'    Fetching: {url}')
                response = self.session.get(url, timeout=20)
                response.raise_for_status()
                self.stdout.write(self.style.SUCCESS(f'    ✓ Success'))
                return response.text
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.WARNING(f'    ⚠ Attempt {attempt + 1} failed: {e}'))
                if attempt < retries - 1:
                    time.sleep(2)
        return None
    
    def discover_categories(self):
        """Discover categories from the website"""
        self.stdout.write('\n' + self.style.SUCCESS('Step 1: Discovering Categories'))
        self.stdout.write('-' * 70)
        
        categories = []
        
        # Try main category page
        urls_to_check = [
            f'{self.base_url}/product-category/',
            f'{self.base_url}/shop/',
            self.base_url,
        ]
        
        for url in urls_to_check:
            html = self.fetch_page(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find category links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/product-category/' in href:
                        # Extract category name and slug
                        cat_slug = href.split('/product-category/')[-1].strip('/')
                        cat_name = link.get_text(strip=True)
                        
                        if cat_name and len(cat_name) > 2 and cat_slug:
                            cat_url = urljoin(self.base_url, href)
                            
                            # Avoid duplicates
                            if not any(c['slug'] == cat_slug for c in categories):
                                categories.append({
                                    'name': cat_name,
                                    'slug': cat_slug,
                                    'url': cat_url
                                })
                                self.stdout.write(self.style.SUCCESS(f'  ✓ Found: {cat_name}'))
        
        # Fallback to known categories if nothing found
        if not categories:
            self.stdout.write(self.style.WARNING('  ⚠ No categories found via scraping, using defaults'))
            categories = [
                {'name': 'Smart Switches/Sockets', 'slug': 'smart-switches-sockets', 
                 'url': f'{self.base_url}/product-category/smart-switches-sockets/'},
                {'name': 'Smart Security', 'slug': 'smart-security',
                 'url': f'{self.base_url}/product-category/smart-security/'},
                {'name': 'Smart Cameras', 'slug': 'smart-cameras',
                 'url': f'{self.base_url}/product-category/smart-cameras/'},
                {'name': 'Smart Locks', 'slug': 'smart-locks',
                 'url': f'{self.base_url}/product-category/smart-locks/'},
                {'name': 'Smart Lighting', 'slug': 'smart-lighting',
                 'url': f'{self.base_url}/product-category/smart-lighting/'},
                {'name': 'Smart Blinds', 'slug': 'smart-blinds',
                 'url': f'{self.base_url}/product-category/smart-blinds/'},
                {'name': 'Smart Speakers', 'slug': 'smart-speakers',
                 'url': f'{self.base_url}/product-category/smart-speakers/'},
                {'name': 'Solar Inverters', 'slug': 'solar-inverters',
                 'url': f'{self.base_url}/product-category/solar-inverters/'},
            ]
        
        self.stdout.write(self.style.SUCCESS(f'\n  Total categories: {len(categories)}'))
        return categories
    
    def scrape_category_products(self, category_data, limit=100):
        """Get product URLs from a category"""
        self.stdout.write(f'\n  Category: {category_data["name"]}')
        
        html = self.fetch_page(category_data['url'])
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        product_urls = []
        
        # Find all product links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '/product/' in href and '/product-category/' not in href:
                prod_url = urljoin(self.base_url, href)
                if prod_url not in product_urls:
                    product_urls.append(prod_url)
        
        product_urls = product_urls[:limit]
        self.stdout.write(self.style.SUCCESS(f'    ✓ Found {len(product_urls)} products'))
        
        return product_urls
    
    def scrape_product_detail(self, url, category_name):
        """Scrape detailed product information"""
        html = self.fetch_page(url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        try:
            # Product name
            name_elem = soup.find('h1', class_=re.compile(r'product[_-]?title|entry-title'))
            if not name_elem:
                name_elem = soup.find('h1')
            product_name = name_elem.get_text(strip=True) if name_elem else None
            
            if not product_name:
                self.stdout.write(self.style.WARNING(f'    ⚠ No product name found'))
                return None
            
            self.stdout.write(f'    Product: {product_name}')
            
            # Price
            price = None
            discount_price = None
            
            price_container = soup.find('p', class_='price')
            if price_container:
                # Check for sale price
                sale_elem = price_container.find('ins')
                regular_elem = price_container.find('del')
                
                if sale_elem and regular_elem:
                    discount_price = self.extract_price(sale_elem.get_text())
                    price = self.extract_price(regular_elem.get_text())
                elif sale_elem:
                    discount_price = self.extract_price(sale_elem.get_text())
                    price = discount_price
                elif regular_elem:
                    price = self.extract_price(regular_elem.get_text())
                else:
                    price = self.extract_price(price_container.get_text())
            
            # Description
            description = ""
            desc_section = soup.find('div', class_=re.compile(r'woocommerce-product-details|product-description'))
            if desc_section:
                paragraphs = desc_section.find_all('p')
                description = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            # Short description
            short_desc_elem = soup.find('div', class_='woocommerce-product-details__short-description')
            short_description = short_desc_elem.get_text(strip=True) if short_desc_elem else (description[:300] if description else product_name)
            
            # SKU
            sku_elem = soup.find('span', class_='sku')
            sku = sku_elem.get_text(strip=True) if sku_elem else f"RZM-{slugify(product_name)[:40].upper()}"
            
            # Images
            main_image_url = None
            gallery_images = []
            
            # Main product image
            main_img = soup.find('img', class_=re.compile(r'wp-post-image|woocommerce-main-image'))
            if not main_img:
                main_img = soup.find('div', class_=re.compile(r'woocommerce-product-gallery')).find('img') if soup.find('div', class_=re.compile(r'woocommerce-product-gallery')) else None
            
            if main_img:
                main_image_url = main_img.get('src') or main_img.get('data-src') or main_img.get('data-lazy-src')
            
            # Gallery images
            gallery_section = soup.find('div', class_=re.compile(r'woocommerce-product-gallery|product-images'))
            if gallery_section:
                for img in gallery_section.find_all('img'):
                    img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                    if img_url and img_url != main_image_url:
                        gallery_images.append(img_url)
            
            # Features
            features = []
            feature_lists = soup.find_all('ul', class_=re.compile(r'feature|spec'))
            if not feature_lists:
                # Try finding any ul in description
                if desc_section:
                    feature_lists = desc_section.find_all('ul')
            
            for ul in feature_lists[:1]:  # Take first list
                for li in ul.find_all('li'):
                    feature = li.get_text(strip=True)
                    if feature and len(feature) > 3:
                        features.append(feature)
            
            features_text = '\n'.join(features[:10]) if features else "Smart home technology\nRemote control capability\nEnergy efficient"
            
            # Stock status
            stock_elem = soup.find('p', class_='stock')
            is_available = True
            stock_qty = 15
            
            if stock_elem:
                stock_text = stock_elem.get_text().lower()
                if 'out of stock' in stock_text or 'sold out' in stock_text:
                    is_available = False
                    stock_qty = 0
            
            # Determine product type
            product_type = 'accessory'
            name_lower = product_name.lower()
            category_lower = category_name.lower()
            
            if 'lock' in name_lower or 'lock' in category_lower:
                product_type = 'smart_lock'
            elif any(word in name_lower or word in category_lower for word in ['camera', 'security', 'alarm', 'sensor', 'cctv']):
                product_type = 'smart_shield'
            
            # Connectivity
            connectivity = 'wifi'
            desc_text = (description + ' ' + product_name).lower()
            if 'bluetooth' in desc_text:
                connectivity = 'bluetooth'
            elif 'zigbee' in desc_text:
                connectivity = 'zigbee'
            elif 'z-wave' in desc_text or 'zwave' in desc_text:
                connectivity = 'zwave'
            
            product_data = {
                'name': product_name,
                'slug': slugify(product_name),
                'category': category_name,
                'product_type': product_type,
                'sku': sku,
                'short_description': short_description[:500],
                'description': description or short_description,
                'features': features_text,
                'price': price or Decimal('0.00'),
                'discount_price': discount_price,
                'brand': 'Ritzman Smart Homes',
                'model_number': sku,
                'connectivity': connectivity,
                'power_source': 'AC Power / Battery',
                'warranty_period': '1 Year',
                'stock_quantity': stock_qty,
                'is_available': is_available,
                'main_image_url': main_image_url,
                'gallery_images': gallery_images[:4],  # Limit to 4 gallery images
                'url': url
            }
            
            self.stdout.write(self.style.SUCCESS(f'      ✓ Extracted product data'))
            return product_data
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'      ✗ Error: {e}'))
            return None
    
    def save_to_database(self, categories, products):
        """Save scraped data to database"""
        self.stdout.write('\n' + self.style.SUCCESS('Step 3: Saving to Database'))
        self.stdout.write('-' * 70)
        
        # Create categories
        self.stdout.write('\n  Creating categories...')
        category_objects = {}
        
        for cat_data in categories:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': f"Browse our selection of {cat_data['name']}",
                    'is_active': True
                }
            )
            category_objects[cat_data['name']] = category
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'    ✓ Created: {category.name}'))
            else:
                self.stdout.write(f'    ○ Exists: {category.name}')
        
        # Create products
        self.stdout.write('\n  Creating products...')
        created_count = 0
        updated_count = 0
        
        for prod_data in products:
            try:
                category = category_objects.get(prod_data['category'])
                if not category:
                    self.stdout.write(self.style.WARNING(f'    ⚠ No category for: {prod_data["name"]}'))
                    continue
                
                product, created = Product.objects.get_or_create(
                    sku=prod_data['sku'],
                    defaults={
                        'name': prod_data['name'],
                        'slug': prod_data['slug'],
                        'category': category,
                        'product_type': prod_data['product_type'],
                        'short_description': prod_data['short_description'],
                        'description': prod_data['description'],
                        'features': prod_data['features'],
                        'price': prod_data['price'],
                        'discount_price': prod_data['discount_price'],
                        'brand': prod_data['brand'],
                        'model_number': prod_data['model_number'],
                        'connectivity': prod_data['connectivity'],
                        'power_source': prod_data['power_source'],
                        'warranty_period': prod_data['warranty_period'],
                        'stock_quantity': prod_data['stock_quantity'],
                        'is_available': prod_data['is_available'],
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'    ✓ Created: {product.name}'))
                else:
                    updated_count += 1
                    self.stdout.write(f'    ○ Exists: {product.name}')
                
                # Download and save main image
                if prod_data.get('main_image_url'):
                    if not product.main_image or created:
                        self.stdout.write(f'      Downloading main image...')
                        image_file = self.download_image(prod_data['main_image_url'], product.name)
                        if image_file:
                            product.main_image = image_file
                            product.save()
                            self.stdout.write(self.style.SUCCESS(f'      ✓ Main image saved'))
                
                # Download and save gallery images
                for i, img_url in enumerate(prod_data.get('gallery_images', [])[:3]):
                    self.stdout.write(f'      Downloading gallery image {i+1}...')
                    image_file = self.download_image(img_url, f"{product.name}-{i+1}")
                    if image_file:
                        prod_img, img_created = ProductImage.objects.get_or_create(
                            product=product,
                            order=i,
                            defaults={
                                'image': image_file,
                                'alt_text': f"{product.name} - View {i+1}"
                            }
                        )
                        if img_created:
                            self.stdout.write(self.style.SUCCESS(f'      ✓ Gallery image {i+1} saved'))
                
                time.sleep(0.5)  # Small delay between products
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error saving {prod_data.get("name")}: {e}'))
        
        # Summary
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(self.style.SUCCESS(f'  Categories: {len(category_objects)}'))
        self.stdout.write(self.style.SUCCESS(f'  Products Created: {created_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Products Already Existed: {updated_count}'))
        self.stdout.write(self.style.SUCCESS(f'  Total Products: {created_count + updated_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
    
    def run(self, specific_category=None, limit=100):
        """Main scraper execution"""
        # Step 1: Discover categories
        categories = self.discover_categories()
        
        if specific_category:
            categories = [c for c in categories if c['slug'] == specific_category or c['name'] == specific_category]
            if not categories:
                self.stdout.write(self.style.ERROR(f'Category "{specific_category}" not found'))
                return
        
        # Step 2: Scrape products
        self.stdout.write('\n' + self.style.SUCCESS('Step 2: Scraping Products'))
        self.stdout.write('-' * 70)
        
        all_products = []
        
        for cat_data in categories:
            product_urls = self.scrape_category_products(cat_data, limit)
            
            for i, prod_url in enumerate(product_urls, 1):
                self.stdout.write(f'\n  [{i}/{len(product_urls)}]')
                product_data = self.scrape_product_detail(prod_url, cat_data['name'])
                
                if product_data:
                    all_products.append(product_data)
                
                time.sleep(1)  # Be polite to the server
        
        # Step 3: Save to database
        if all_products:
            self.save_to_database(categories, all_products)
        else:
            self.stdout.write(self.style.WARNING('\n⚠ No products scraped'))