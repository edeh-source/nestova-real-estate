"""
Create Local Placeholder Images for Products
This generates images locally without external API calls
Usage: python manage.py create_local_images
"""

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from shop.models import Product
from PIL import Image, ImageDraw, ImageFont
import io


class Command(BaseCommand):
    help = 'Create local placeholder images for products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Recreate images even if products already have them',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Creating Local Placeholder Images'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        force = options.get('force', False)
        
        # Get products
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
        
        for i, product in enumerate(products, 1):
            self.stdout.write(f'\n[{i}/{products.count()}] Processing: {product.name}')
            
            try:
                # Create image
                image = self.create_product_image(product)
                
                # Save to BytesIO
                img_io = io.BytesIO()
                image.save(img_io, format='PNG', quality=85)
                img_io.seek(0)
                
                # Save to product
                filename = f"{product.slug[:50]}.png"
                product.main_image.save(filename, ContentFile(img_io.read()), save=True)
                
                updated += 1
                self.stdout.write(self.style.SUCCESS('    ✓ Image created and saved'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    ✗ Error: {e}'))
        
        self.stdout.write('\n' + self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS(f'✓ Complete! Created {updated} images'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
    
    def create_product_image(self, product):
        """Create a placeholder image for the product"""
        # Image size
        width, height = 800, 600
        
        # Get color based on category
        bg_color = self.get_category_color(product.category.name)
        
        # Create image
        image = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)
        
        # Add gradient effect
        for i in range(height):
            alpha = int(255 * (1 - i / height * 0.3))
            color = tuple(max(0, c - int(50 * i / height)) for c in bg_color)
            draw.line([(0, i), (width, i)], fill=color)
        
        # Add product name
        text = product.name
        
        # Try to use a nice font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 40)
            small_font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Calculate text position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Wrap text if too long
        if text_width > width - 100:
            words = text.split()
            lines = []
            current_line = []
            
            for word in words:
                test_line = ' '.join(current_line + [word])
                bbox = draw.textbbox((0, 0), test_line, font=font)
                if bbox[2] - bbox[0] < width - 100:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw wrapped text
            y_offset = (height - len(lines) * 50) // 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                x = (width - line_width) // 2
                
                # Shadow
                draw.text((x + 2, y_offset + 2), line, fill=(0, 0, 0, 128), font=font)
                # Text
                draw.text((x, y_offset), line, fill='white', font=font)
                y_offset += 50
        else:
            x = (width - text_width) // 2
            y = (height - text_height) // 2
            
            # Shadow
            draw.text((x + 2, y + 2), text, fill=(0, 0, 0, 128), font=font)
            # Text
            draw.text((x, y), text, fill='white', font=font)
        
        # Add category badge
        category_text = product.category.name
        bbox = draw.textbbox((0, 0), category_text, font=small_font)
        badge_width = bbox[2] - bbox[0] + 40
        badge_height = bbox[3] - bbox[1] + 20
        
        # Badge background
        badge_x = width - badge_width - 20
        badge_y = 20
        draw.rectangle(
            [badge_x, badge_y, badge_x + badge_width, badge_y + badge_height],
            fill=(255, 255, 255, 200),
            outline=(200, 200, 200)
        )
        
        # Badge text
        text_x = badge_x + 20
        text_y = badge_y + 10
        draw.text((text_x, text_y), category_text, fill=bg_color, font=small_font)
        
        # Add price tag
        if product.discount_price:
            price_text = f"₦{product.discount_price:,.0f}"
        else:
            price_text = f"₦{product.price:,.0f}"
        
        bbox = draw.textbbox((0, 0), price_text, font=small_font)
        price_width = bbox[2] - bbox[0] + 30
        price_height = bbox[3] - bbox[1] + 20
        
        price_x = 20
        price_y = height - price_height - 20
        draw.rectangle(
            [price_x, price_y, price_x + price_width, price_y + price_height],
            fill=(46, 204, 113),
            outline=(39, 174, 96)
        )
        
        text_x = price_x + 15
        text_y = price_y + 10
        draw.text((text_x, text_y), price_text, fill='white', font=small_font)
        
        return image
    
    def get_category_color(self, category_name):
        """Get RGB color for category"""
        colors = {
            'smart switches': (74, 144, 226),      # Blue
            'smart security': (231, 76, 60),       # Red
            'smart cameras': (155, 89, 182),       # Purple
            'smart locks': (46, 204, 113),         # Green
            'smart lighting': (243, 156, 18),      # Orange
            'smart blinds': (26, 188, 156),        # Teal
            'smart speakers': (52, 152, 219),      # Light Blue
            'solar inverters': (230, 126, 34),     # Dark Orange
            'smart appliances': (149, 165, 166),   # Gray
        }
        
        category_lower = category_name.lower()
        for key, color in colors.items():
            if key in category_lower:
                return color
        
        return (127, 140, 141)  # Default gray