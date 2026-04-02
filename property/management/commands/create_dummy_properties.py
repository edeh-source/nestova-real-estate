from django.core.management.base import BaseCommand
from property.models import Property, State, City, PropertyType, PropertyStatus
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.conf import settings
import random
import os
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Generates 20 dummy properties with images (if available)'

    def handle(self, *args, **kwargs):
        self.stdout.write('Generating dummy properties...')

        # 1. Ensure Dependencies Exist
        
        # User
        user, created = User.objects.get_or_create(
            email='admin@nestova.com',
            defaults={
                'username': 'admin_nestova',
                'first_name': 'Admin',
                'last_name': 'User',
                'is_staff': True,
                'is_superuser': True,
                'phone_number': '+2348000000000'  # Add required phone number
            }
        )
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write(f'Created user: {user.email}')

        # States & Cities
        state, _ = State.objects.get_or_create(name='Lagos', code='LA')
        cities_names = ['Lekki', 'Ikeja', 'Victoria Island', 'Ikoyi', 'Ajah']
        cities = []
        for name in cities_names:
            city, _ = City.objects.get_or_create(name=name, state=state)
            cities.append(city)

        # Property Types
        types_data = [
            ('detached_house', 'residential', 'Detached House'),
            ('flat', 'residential', 'Flat/Apartment'),
            ('land', 'land', 'Land'),
            ('office', 'commercial', 'Office Space')
        ]
        
        property_types = []
        for code, cat, name in types_data:
            pt, _ = PropertyType.objects.get_or_create(
                name=code,
                defaults={'category': cat, 'description': name}
            )
            property_types.append(pt)

        # Property Status
        statuses_data = ['for_sale', 'for_rent', 'sold']
        property_statuses = []
        for code in statuses_data:
            ps, _ = PropertyStatus.objects.get_or_create(name=code)
            property_statuses.append(ps)

        # Image Source - Check if directory exists
        available_images = []
        static_img_dir = os.path.join(settings.BASE_DIR, 'static', 'assets', 'img', 'real-estate')
        
        # Only try to list images if the directory exists
        if os.path.exists(static_img_dir) and os.path.isdir(static_img_dir):
            try:
                available_images = [
                    f for f in os.listdir(static_img_dir) 
                    if f.startswith('property-') and f.endswith('.webp')
                ]
                self.stdout.write(f'Found {len(available_images)} images in static directory')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Could not read images: {e}'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Static image directory not found: {static_img_dir}. '
                'Properties will be created without images.'
            ))

        # 2. Create Properties
        titles = [
            'Luxury Villa with Pool', 'Modern Apartment in City Center', 'Spacious Family Home', 
            'Cozy Studio', 'Prime Commercial Land', 'Seaside Mansion', 'Executive Office Suite',
            'Renovated Duplex', 'Penthouse with View', 'Affordable Starter Home'
        ]

        for i in range(20):
            prop_type = random.choice(property_types)
            status = random.choice(property_statuses)
            is_rent = status.name == 'for_rent'
            
            price = Decimal(random.randint(1, 500) * 1000000) if not is_rent else Decimal(random.randint(50, 500) * 10000)
            
            p = Property(
                title=f"{random.choice(titles)} {i+1}",
                description=f"This is a dummy description for property {i+1}. It features amazing amenities and a great location.",
                state=state,
                city=random.choice(cities),
                address=f"{random.randint(1, 999)} Dummy Street",
                property_type=prop_type,
                status=status,
                bedrooms=random.randint(1, 6),
                bathrooms=random.randint(1, 5),
                square_feet=random.randint(500, 5000),
                price=price,
                listed_by=user,
                is_featured=random.choice([True, False]),
                is_new=random.choice([True, False])
            )
            
            # Save first to get ID/Slug
            p.save()

            # Attach Image - Only if images are available
            if available_images:
                img_name = random.choice(available_images)
                img_path = os.path.join(static_img_dir, img_name)
                
                try:
                    # Copy file to media
                    with open(img_path, 'rb') as f:
                        p.featured_image.save(
                            f"dummy_{i}_{img_name}", 
                            ContentFile(f.read()), 
                            save=True
                        )
                    self.stdout.write(f'✅ Created Property: {p.title} (with image)')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'⚠️  Created Property: {p.title} (without image - {e})'
                    ))
            else:
                self.stdout.write(f'✅ Created Property: {p.title} (no images available)')

        self.stdout.write(self.style.SUCCESS('Successfully created 20 dummy properties'))