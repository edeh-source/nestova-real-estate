"""
Ritzman Smart Homes Product Scraper
This script crawls https://ritzmansmarthomes.com/ to extract all categories and products
and populates them into your Django database.

Requirements:
    pip install selenium beautifulsoup4 lxml requests pillow django --break-system-packages
    
You'll also need to download ChromeDriver or use webdriver-manager:
    pip install webdriver-manager --break-system-packages
"""

import os
import sys
import django
import requests
import time
import re
from decimal import Decimal
from io import BytesIO
from urllib.parse import urljoin, urlparse
from datetime import datetime

# Setup Django
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')  
django.setup()

from django.core.files import File
from django.core.files.base import ContentFile
from django.utils.text import slugify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

# Import your models (adjust the import path as needed)
from shop.models import Category, Product, ProductImage, ProductSpecification


class RitzmanScraper:
    def __init__(self):
        self.base_url = "https://ritzmansmarthomes.com"
        self.driver = None
        self.categories_data = []
        self.products_data = []
        
    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        try:
            # Option 1: Use webdriver-manager (recommended)
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except ImportError:
            # Option 2: Use system ChromeDriver
            self.driver = webdriver.Chrome(options=chrome_options)
            
        self.driver.implicitly_wait(10)
        print("✓ WebDriver initialized")
    
    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            print("✓ WebDriver closed")
    
    def extract_price(self, price_text):
        """Extract numeric price from text"""
        if not price_text:
            return None
        # Remove currency symbols and commas
        price_text = re.sub(r'[₦N,\s]', '', price_text)
        # Extract first number found
        match = re.search(r'[\d.]+', price_text)
        if match:
            try:
                return Decimal(match.group())
            except:
                return None
        return None
    
    def download_image(self, image_url):
        """Download image and return Django File object"""
        try:
            if not image_url or image_url.startswith('data:'):
                return None
                
            # Make it absolute URL
            if not image_url.startswith('http'):
                image_url = urljoin(self.base_url, image_url)
            
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Get filename from URL
                filename = os.path.basename(urlparse(image_url).path)
                if not filename:
                    filename = 'image.jpg'
                
                return ContentFile(response.content, name=filename)
        except Exception as e:
            print(f"  ⚠ Error downloading image {image_url}: {e}")
        return None
    
    def scrape_categories(self):
        """Scrape all product categories"""
        print("\n" + "="*60)
        print("STEP 1: Scraping Categories")
        print("="*60)
        
        category_urls = [
            f"{self.base_url}/product-category/",
            f"{self.base_url}/shop/",
        ]
        
        # Known categories from search results
        known_categories = [
            ('Smart Switches/Sockets', 'smart-switches-sockets'),
            ('Smart Appliances', 'smart-appliances'),
            ('Smart Security', 'smart-security'),
            ('Smart Lighting', 'smart-lighting'),
            ('Smart Cameras', 'smart-cameras'),
            ('Smart Locks', 'smart-locks'),
            ('Smart Blinds', 'smart-blinds'),
            ('Smart Speakers', 'smart-speakers'),
            ('Solar Inverters', 'solar-inverters'),
        ]
        
        categories_found = set()
        
        for url in category_urls:
            try:
                print(f"\nChecking: {url}")
                self.driver.get(url)
                time.sleep(3)
                
                soup = BeautifulSoup(self.driver.page_source, 'lxml')
                
                # Look for category links
                category_links = soup.find_all('a', href=re.compile(r'/product-category/'))
                
                for link in category_links:
                    cat_url = link.get('href', '')
                    cat_name = link.get_text(strip=True)
                    
                    if cat_name and len(cat_name) > 2:
                        cat_slug = cat_url.split('product-category/')[-1].strip('/')
                        if cat_slug and (cat_name, cat_slug) not in categories_found:
                            categories_found.add((cat_name, cat_slug))
                            print(f"  ✓ Found: {cat_name}")
                
            except Exception as e:
                print(f"  ⚠ Error scraping {url}: {e}")
        
        # Add known categories
        for cat_name, cat_slug in known_categories:
            if (cat_name, cat_slug) not in categories_found:
                categories_found.add((cat_name, cat_slug))
        
        # Store category data
        self.categories_data = [
            {
                'name': name,
                'slug': slug,
                'url': f"{self.base_url}/product-category/{slug}/"
            }
            for name, slug in categories_found
        ]
        
        print(f"\n✓ Total categories found: {len(self.categories_data)}")
        return self.categories_data
    
    def scrape_products_from_category(self, category_data):
        """Scrape all products from a specific category"""
        cat_name = category_data['name']
        cat_url = category_data['url']
        
        print(f"\n  Scraping products from: {cat_name}")
        products = []
        
        try:
            self.driver.get(cat_url)
            time.sleep(3)
            
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            
            # Find product links
            product_links = soup.find_all('a', href=re.compile(r'/product/'))
            product_urls = set()
            
            for link in product_links:
                url = link.get('href', '')
                if '/product/' in url and url not in product_urls:
                    product_urls.add(url)
            
            print(f"    Found {len(product_urls)} product URLs")
            
            # Scrape each product
            for i, prod_url in enumerate(product_urls, 1):
                print(f"    [{i}/{len(product_urls)}] Scraping: {prod_url}")
                product_data = self.scrape_product_detail(prod_url, cat_name)
                if product_data:
                    products.append(product_data)
                time.sleep(1)  # Be polite
                
        except Exception as e:
            print(f"    ⚠ Error scraping category {cat_name}: {e}")
        
        return products
    
    def scrape_product_detail(self, product_url, category_name):
        """Scrape detailed product information"""
        try:
            self.driver.get(product_url)
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            
            # Extract product name
            name_elem = soup.find('h1', class_=re.compile(r'product[_-]title|entry-title'))
            if not name_elem:
                name_elem = soup.find('h1')
            product_name = name_elem.get_text(strip=True) if name_elem else 'Unknown Product'
            
            # Extract price
            price = None
            discount_price = None
            
            price_elem = soup.find('p', class_='price')
            if price_elem:
                # Check for sale price
                sale_price = price_elem.find('ins')
                regular_price = price_elem.find('del')
                
                if sale_price:
                    discount_price = self.extract_price(sale_price.get_text())
                    if regular_price:
                        price = self.extract_price(regular_price.get_text())
                    else:
                        price = discount_price
                else:
                    # Regular price only
                    price_text = price_elem.get_text(strip=True)
                    price = self.extract_price(price_text)
            
            # Extract description
            description = ""
            desc_elem = soup.find('div', class_=re.compile(r'product[_-]description|woocommerce-product-details'))
            if desc_elem:
                # Get text from paragraphs
                paragraphs = desc_elem.find_all('p')
                description = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
            
            if not description:
                desc_elem = soup.find('div', {'id': 'tab-description'})
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
            
            # Extract short description
            short_desc_elem = soup.find('div', class_='woocommerce-product-details__short-description')
            short_description = short_desc_elem.get_text(strip=True) if short_desc_elem else description[:200]
            
            # Extract images
            images = []
            main_image_url = None
            
            # Main image
            main_img = soup.find('img', class_=re.compile(r'wp-post-image|attachment-.*full'))
            if main_img:
                main_image_url = main_img.get('src') or main_img.get('data-src')
            
            # Gallery images
            gallery = soup.find_all('img', class_=re.compile(r'attachment-|gallery'))
            for img in gallery:
                img_url = img.get('src') or img.get('data-src')
                if img_url and img_url != main_image_url:
                    images.append(img_url)
            
            # Extract SKU
            sku_elem = soup.find('span', class_='sku')
            sku = sku_elem.get_text(strip=True) if sku_elem else f"SKU-{slugify(product_name)[:50]}"
            
            # Extract brand
            brand = "Ritzman Smart Homes"
            
            # Stock status
            stock_status = soup.find('p', class_='stock')
            is_available = True
            stock_quantity = 10  # Default
            
            if stock_status:
                stock_text = stock_status.get_text().lower()
                if 'out of stock' in stock_text:
                    is_available = False
                    stock_quantity = 0
            
            # Determine product type based on category or name
            product_type = 'accessory'
            name_lower = product_name.lower()
            if 'lock' in name_lower:
                product_type = 'smart_lock'
            elif any(word in name_lower for word in ['camera', 'security', 'alarm', 'sensor']):
                product_type = 'smart_shield'
            
            # Determine connectivity
            connectivity = 'wifi'
            if 'bluetooth' in name_lower or 'bt' in name_lower:
                connectivity = 'bluetooth'
            elif 'zigbee' in name_lower:
                connectivity = 'zigbee'
            elif 'z-wave' in name_lower or 'zwave' in name_lower:
                connectivity = 'zwave'
            
            product_data = {
                'name': product_name,
                'slug': slugify(product_name),
                'category': category_name,
                'product_type': product_type,
                'sku': sku,
                'short_description': short_description[:500],
                'description': description or short_description,
                'features': self.extract_features(soup),
                'price': price or Decimal('0.00'),
                'discount_price': discount_price,
                'brand': brand,
                'model_number': sku,
                'connectivity': connectivity,
                'power_source': self.extract_power_source(soup),
                'warranty_period': '1 Year',
                'stock_quantity': stock_quantity,
                'is_available': is_available,
                'main_image_url': main_image_url,
                'gallery_images': images,
                'specifications': self.extract_specifications(soup),
                'url': product_url
            }
            
            return product_data
            
        except Exception as e:
            print(f"      ⚠ Error scraping product: {e}")
            return None
    
    def extract_features(self, soup):
        """Extract product features from description"""
        features = []
        
        # Look for lists in description
        feature_lists = soup.find_all('ul')
        for ul in feature_lists:
            for li in ul.find_all('li'):
                feature = li.get_text(strip=True)
                if feature and len(feature) > 5:
                    features.append(feature)
        
        if features:
            return '\n'.join(features[:10])  # Limit to 10 features
        
        return "Smart connectivity\nRemote control via app\nEnergy efficient\nEasy installation"
    
    def extract_power_source(self, soup):
        """Extract power source information"""
        desc_text = soup.get_text().lower()
        
        if 'battery' in desc_text:
            return 'Battery Powered'
        elif 'solar' in desc_text:
            return 'Solar Powered'
        elif 'hardwired' in desc_text or 'wired' in desc_text:
            return 'Hardwired'
        else:
            return 'AC Power / Battery'
    
    def extract_specifications(self, soup):
        """Extract technical specifications"""
        specs = []
        
        # Look for specification tables
        spec_tables = soup.find_all('table', class_=re.compile(r'spec|attribute|additional'))
        
        for table in spec_tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    spec_name = cells[0].get_text(strip=True)
                    spec_value = cells[1].get_text(strip=True)
                    if spec_name and spec_value:
                        specs.append({
                            'spec_name': spec_name,
                            'spec_value': spec_value
                        })
        
        return specs
    
    def save_to_database(self):
        """Save scraped data to Django database"""
        print("\n" + "="*60)
        print("STEP 3: Saving to Database")
        print("="*60)
        
        # Save categories
        print("\nSaving categories...")
        category_objects = {}
        
        for cat_data in self.categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': f"Browse our selection of {cat_data['name']} products",
                    'is_active': True
                }
            )
            category_objects[cat_data['name']] = category
            status = "✓ Created" if created else "○ Exists"
            print(f"  {status}: {category.name}")
        
        # Save products
        print(f"\nSaving {len(self.products_data)} products...")
        created_count = 0
        updated_count = 0
        
        for prod_data in self.products_data:
            try:
                # Get or create product
                category = category_objects.get(prod_data['category'])
                if not category:
                    print(f"  ⚠ Category not found for: {prod_data['name']}")
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
                    print(f"  ✓ Created: {product.name}")
                else:
                    updated_count += 1
                    print(f"  ○ Exists: {product.name}")
                
                # Download and save main image
                if prod_data.get('main_image_url') and not product.main_image:
                    image_file = self.download_image(prod_data['main_image_url'])
                    if image_file:
                        product.main_image = image_file
                        product.save()
                        print(f"    → Main image saved")
                
                # Save gallery images
                for i, img_url in enumerate(prod_data.get('gallery_images', [])[:5]):
                    image_file = self.download_image(img_url)
                    if image_file:
                        ProductImage.objects.get_or_create(
                            product=product,
                            image=image_file,
                            defaults={
                                'alt_text': f"{product.name} - Image {i+1}",
                                'order': i
                            }
                        )
                
                # Save specifications
                for j, spec in enumerate(prod_data.get('specifications', [])):
                    ProductSpecification.objects.get_or_create(
                        product=product,
                        spec_name=spec['spec_name'],
                        defaults={
                            'spec_value': spec['spec_value'],
                            'order': j
                        }
                    )
                
            except Exception as e:
                print(f"  ⚠ Error saving {prod_data.get('name', 'Unknown')}: {e}")
        
        print(f"\n" + "="*60)
        print(f"✓ Database Save Complete!")
        print(f"  Categories: {len(category_objects)}")
        print(f"  Products Created: {created_count}")
        print(f"  Products Updated: {updated_count}")
        print("="*60)
    
    def run(self):
        """Main execution method"""
        print("\n" + "="*60)
        print("Ritzman Smart Homes Scraper")
        print("="*60)
        
        try:
            # Setup
            self.setup_driver()
            
            # Scrape categories
            self.scrape_categories()
            
            # Scrape products from each category
            print("\n" + "="*60)
            print("STEP 2: Scraping Products")
            print("="*60)
            
            for cat_data in self.categories_data:
                products = self.scrape_products_from_category(cat_data)
                self.products_data.extend(products)
            
            print(f"\n✓ Total products scraped: {len(self.products_data)}")
            
            # Save to database
            if self.products_data:
                self.save_to_database()
            else:
                print("\n⚠ No products found to save")
            
        except Exception as e:
            print(f"\n⚠ Error during scraping: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.close_driver()


if __name__ == '__main__':
    scraper = RitzmanScraper()
    scraper.run()