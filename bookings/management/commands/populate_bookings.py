import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from bookings.models import Apartment, ApartmentChoice

User = get_user_model()

class Command(BaseCommand):
    help = 'Populate the database with 20 professional apartment listings for the booking app'

    def handle(self, *args, **options):
        self.stdout.write("Starting population of professional apartment listings...")
        
        # 1. Ensure we have an owner
        owner = User.objects.filter(is_superuser=True).first()
        if not owner:
            owner, created = User.objects.get_or_create(
                username='admin',
                defaults={'email': 'admin@nestova.com', 'is_staff': True, 'is_superuser': True}
            )
            if created:
                owner.set_password('nestova_admin_2024')
                owner.save()
                self.stdout.write(self.style.SUCCESS(f"Created default superuser: {owner.username}"))

        # 2. Ensure we have ApartmentChoice types
        choices = [
            'Luxury Penthouse', 'Standard Studio', 'Executive 2-Bedroom', 
            'Premium 3-Bedroom', 'Serviced Mini-Flat', 'Terrace Duplex'
        ]
        choice_objs = []
        for choice_name in choices:
            obj, created = ApartmentChoice.objects.get_or_create(
                name=choice_name,
                defaults={'slug': slugify(choice_name)}
            )
            choice_objs.append(obj)

        # 3. Nigerian Locations
        locations = [
            ('Ikoyi', 'Lagos', 'LA', '101233'),
            ('Lekki Phase 1', 'Lagos', 'LA', '105102'),
            ('Victoria Island', 'Lagos', 'LA', '101241'),
            ('Maitama', 'Abuja', 'FCT', '900271'),
            ('Asokoro', 'Abuja', 'FCT', '900231'),
            ('Wuse II', 'Abuja', 'FCT', '900288'),
            ('GRA Phase 2', 'Port Harcourt', 'Rivers', '500272'),
            ('Old GRA', 'Port Harcourt', 'Rivers', '500261'),
            ('Banana Island', 'Lagos', 'LA', '101233'),
            ('Eko Atlantic', 'Lagos', 'LA', '101241'),
        ]

        # 4. Professional Descriptions
        descriptions = [
            """
            <p>Experience the epitome of luxury living in this architectural masterpiece. Situated in the exclusive enclave of {area}, this apartment offers breathtaking views of the city skyline.</p>
            <p><strong>Exquisite Features:</strong></p>
            <ul>
                <li>Master-crafted interiors with imported marble flooring</li>
                <li>State-of-the-art kitchen with integrated Bosch appliances</li>
                <li>Expansive floor-to-ceiling windows providing abundant natural light</li>
                <li>Automated smart-home system for climate and security control</li>
            </ul>
            <p>Designed for those who demand excellence, this residence combines sophisticated aesthetics with unparalleled comfort. Enjoy 24/7 concierge service and world-class amenities within the facility.</p>
            """,
            """
            <p>A contemporary sanctuary designed for the modern professional. This impeccably finished apartment in {area} offers a seamless blend of style and functionality.</p>
            <p><strong>Key Highlights:</strong></p>
            <ul>
                <li>Open-plan living area perfect for hosting and relaxation</li>
                <li>Premium sanitary wares and walk-in showers</li>
                <li>Dedicated work-from-home space with high-speed fiber connectivity</li>
                <li>Private balcony overlooking meticulously landscaped gardens</li>
            </ul>
            <p>Located within walking distance to premium dining and retail outlets, this property ensures you are at the heart of the city's vibrant lifestyle while maintaining a serene private retreat.</p>
            """,
            """
            <p>Redefine your lifestyle in this ultra-modern residence located in the prestigious {area}. Every detail has been curated to provide a premium living experience.</p>
            <p><strong>Sophisticated Living:</strong></p>
            <ul>
                <li>Chef's kitchen with granite countertops and custom cabinetry</li>
                <li>Master suite featuring a bespoke walk-in closet and spa-like ensuite</li>
                <li>Energy-efficient lighting and localized climate control</li>
                <li>Underground secured parking with direct elevator access</li>
            </ul>
            <p>This property is a statement of success and refinement, offering the perfect balance of exclusivity and accessibility in one of Nigeria's most coveted addresses.</p>
            """
        ]

        titles_prefixes = ['The Royal', 'Azure', 'Starlight', 'Platinum', 'The Grand', 'Serenity', 'Elite', 'Ambassador', 'Heritage', 'Modernist']
        titles_suffixes = ['Suites', 'Residences', 'Court', 'Manor', 'Towers', 'Apartments', 'Lodge', 'Villa']

        # 5. Create 20 Apartments
        for i in range(20):
            area, city, state, zip_code = random.choice(locations)
            choice = random.choice(choice_objs)
            desc_template = random.choice(descriptions)
            
            prefix = random.choice(titles_prefixes)
            suffix = random.choice(titles_suffixes)
            title = f"{prefix} {choice.name} {suffix} - {area}"
            
            # Pricing based on type and area
            base_price = Decimal(random.randint(45000, 150000))
            if 'Luxury' in choice.name or 'Penthouse' in choice.name:
                base_price += Decimal(random.randint(100000, 250000))
            if area in ['Ikoyi', 'Maitama', 'Banana Island']:
                base_price *= Decimal('1.5')

            sq_ft = random.randint(800, 3500)
            bedrooms = 1
            if '2-Bedroom' in choice.name: bedrooms = 2
            elif '3-Bedroom' in choice.name or 'Duplex' in choice.name: bedrooms = 3
            elif 'Penthouse' in choice.name: bedrooms = 4

            bathrooms = bedrooms + random.randint(0, 1)

            Apartment.objects.create(
                title=title,
                description=desc_template.format(area=area),
                property_type=choice,
                address=f"Plot {random.randint(1, 400)}, {random.choice(['Glover Road', 'Adetokunbo Ademola', 'Kingsway', 'Ajose Adeogun', 'Herbert Macaulay', 'Ahmadu Bello Way'])}",
                city=city,
                state=state,
                zip_code=zip_code,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                square_feet=sq_ft,
                floor_number=random.randint(1, 15),
                price_per_night=base_price,
                price_per_month=base_price * Decimal('22'),
                security_deposit=base_price * Decimal('2'),
                has_wifi=True,
                has_parking=True,
                has_pool=random.choice([True, False]),
                has_gym=random.choice([True, False]),
                has_ac=True,
                has_heating=False, # Nigeria context
                is_pet_friendly=random.choice([True, False]),
                has_balcony=True,
                has_elevator=True if random.randint(1, 15) > 1 else False,
                status='available',
                owner=owner,
                max_guests=bedrooms * 2
            )
            self.stdout.write(f"Created listing {i+1}: {title}")

        self.stdout.write(self.style.SUCCESS("Successfully created 20 professional apartment listings!"))
