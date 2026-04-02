"""
Management command to create sample apartments in the database.

Usage:
    python manage.py create_sample_apartments
    python manage.py create_sample_apartments --count 50
    python manage.py create_sample_apartments --clear
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal
import random

from bookings.models import Apartment, ApartmentChoice, ApartmentImage

User = get_user_model()


class Command(BaseCommand):
    help = 'Creates sample apartments in the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=20,
            help='Number of apartments to create (default: 20)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing apartments before creating new ones',
        )

    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']

        # Clear existing apartments if requested
        if clear:
            self.stdout.write(self.style.WARNING('Clearing existing apartments...'))
            deleted_count = Apartment.objects.all().count()
            Apartment.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} apartments'))

        # Create property types if they don't exist
        self.stdout.write('Creating property types...')
        property_types = self.create_property_types()
        self.stdout.write(self.style.SUCCESS(f'Created/verified {len(property_types)} property types'))

        # Get or create a default owner
        owner = self.get_or_create_owner()
        self.stdout.write(self.style.SUCCESS(f'Using owner: {owner.username}'))

        # Create apartments
        self.stdout.write(f'Creating {count} sample apartments...')
        created_count = 0
        
        for i in range(count):
            apartment = self.create_apartment(i + 1, property_types, owner)
            if apartment:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {apartment.title}'))

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully created {created_count} apartments!'))

    def create_property_types(self):
        """Create property types"""
        types = [
            'Studio Apartment',
            'One Bedroom Apartment',
            'Two Bedroom Apartment',
            'Three Bedroom Apartment',
            'Penthouse',
            'Loft',
            'Duplex',
            'Luxury Apartment',
        ]
        
        property_types = []
        for type_name in types:
            obj, created = ApartmentChoice.objects.get_or_create(
                name=type_name,
                defaults={'slug': slugify(type_name)}
            )
            property_types.append(obj)
        
        return property_types

    def get_or_create_owner(self):
        """Get or create a default owner for apartments"""
        owner, created = User.objects.get_or_create(
            username='property_owner',
            defaults={
                'email': 'owner@example.com',
                'first_name': 'Property',
                'last_name': 'Owner',
            }
        )
        if created:
            owner.set_password('password123')
            owner.save()
        return owner

    def create_apartment(self, index, property_types, owner):
        """Create a single apartment with realistic data"""
        
        # City and state combinations
        locations = [
            ('New York', 'NY'),
            ('Los Angeles', 'CA'),
            ('Chicago', 'IL'),
            ('Houston', 'TX'),
            ('Phoenix', 'AZ'),
            ('Philadelphia', 'PA'),
            ('San Antonio', 'TX'),
            ('San Diego', 'CA'),
            ('Dallas', 'TX'),
            ('San Jose', 'CA'),
            ('Austin', 'TX'),
            ('Jacksonville', 'FL'),
            ('Fort Worth', 'TX'),
            ('Columbus', 'OH'),
            ('Charlotte', 'NC'),
            ('San Francisco', 'CA'),
            ('Indianapolis', 'IN'),
            ('Seattle', 'WA'),
            ('Denver', 'CO'),
            ('Boston', 'MA'),
        ]
        
        # Street names
        streets = [
            'Main Street', 'Park Avenue', 'Broadway', 'Oak Street', 'Maple Drive',
            'Washington Boulevard', 'Lincoln Avenue', 'Madison Street', 'Jefferson Road',
            'Fifth Avenue', 'Sunset Boulevard', 'Beach Road', 'Harbor View',
            'Mountain View Drive', 'Lake Shore Drive', 'River Road', 'Forest Lane',
            'Garden Street', 'Highland Avenue', 'Valley Road'
        ]
        
        # Apartment name prefixes
        prefixes = [
            'The', 'Luxury', 'Modern', 'Cozy', 'Spacious', 'Elegant',
            'Premium', 'Executive', 'Downtown', 'Uptown', 'Sunset',
            'Skyline', 'Waterfront', 'Parkview', 'Grand', 'Royal'
        ]
        
        # Apartment name suffixes
        suffixes = [
            'Heights', 'Plaza', 'Residence', 'Suites', 'Towers', 'Apartments',
            'Living', 'Homes', 'Estate', 'Village', 'Commons', 'Place'
        ]
        
        # Generate apartment data
        city, state = random.choice(locations)
        street = random.choice(streets)
        prefix = random.choice(prefixes)
        suffix = random.choice(suffixes)
        property_type = random.choice(property_types)
        
        # Generate title
        title = f"{prefix} {property_type.name} in {city}"
        
        # Generate bedrooms and bathrooms based on property type
        if 'Studio' in property_type.name:
            bedrooms = 0
            bathrooms = 1
            square_feet = random.randint(350, 600)
            max_guests = random.randint(1, 2)
        elif 'One Bedroom' in property_type.name:
            bedrooms = 1
            bathrooms = 1
            square_feet = random.randint(600, 900)
            max_guests = random.randint(2, 3)
        elif 'Two Bedroom' in property_type.name:
            bedrooms = 2
            bathrooms = random.choice([1, 2])
            square_feet = random.randint(900, 1400)
            max_guests = random.randint(3, 5)
        elif 'Three Bedroom' in property_type.name:
            bedrooms = 3
            bathrooms = random.choice([2, 3])
            square_feet = random.randint(1400, 2000)
            max_guests = random.randint(4, 6)
        elif 'Penthouse' in property_type.name or 'Luxury' in property_type.name:
            bedrooms = random.randint(2, 4)
            bathrooms = random.randint(2, 4)
            square_feet = random.randint(1800, 3500)
            max_guests = random.randint(4, 8)
        else:
            bedrooms = random.randint(1, 3)
            bathrooms = random.randint(1, 2)
            square_feet = random.randint(700, 1500)
            max_guests = random.randint(2, 5)
        
        # Generate pricing based on location and size
        base_price = square_feet * Decimal('0.15')
        city_multiplier = {
            'New York': 2.5,
            'San Francisco': 2.3,
            'Los Angeles': 1.8,
            'Boston': 1.9,
            'Seattle': 1.7,
            'San Diego': 1.6,
        }
        multiplier = Decimal(str(city_multiplier.get(city, 1.0)))
        price_per_night = (base_price * multiplier).quantize(Decimal('0.01'))
        price_per_month = (price_per_night * Decimal('25')).quantize(Decimal('0.01'))
        security_deposit = (price_per_month * Decimal('0.5')).quantize(Decimal('0.01'))
        
        # Generate description
        description = self.generate_description(
            bedrooms, bathrooms, square_feet, city, property_type.name
        )
        
        # Random amenities
        has_wifi = random.choice([True, True, True, False])  # 75% chance
        has_parking = random.choice([True, True, False, False])  # 50% chance
        has_pool = random.choice([True, False, False, False])  # 25% chance
        has_gym = random.choice([True, True, False, False])  # 50% chance
        has_ac = random.choice([True, True, True, True, False])  # 80% chance
        has_heating = True  # Always true
        is_pet_friendly = random.choice([True, False, False, False])  # 25% chance
        has_balcony = random.choice([True, True, False])  # 66% chance
        has_elevator = random.choice([True, True, True, False])  # 75% chance
        
        # Random status (mostly available)
        status = random.choices(
            ['available', 'booked', 'maintenance'],
            weights=[85, 10, 5]
        )[0]
        
        # Create apartment
        try:
            apartment = Apartment.objects.create(
                title=title,
                slug=slugify(title) + f'-{index}',
                description=description,
                property_type=property_type,
                address=f"{random.randint(100, 9999)} {street}",
                city=city,
                state=state,
                zip_code=str(random.randint(10000, 99999)),
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                square_feet=square_feet,
                floor_number=random.randint(1, 20),
                price_per_night=price_per_night,
                price_per_month=price_per_month,
                security_deposit=security_deposit,
                has_wifi=has_wifi,
                has_parking=has_parking,
                has_pool=has_pool,
                has_gym=has_gym,
                has_ac=has_ac,
                has_heating=has_heating,
                is_pet_friendly=is_pet_friendly,
                has_balcony=has_balcony,
                has_elevator=has_elevator,
                status=status,
                owner=owner,
                max_guests=max_guests,
            )
            return apartment
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating apartment: {str(e)}'))
            return None

    def generate_description(self, bedrooms, bathrooms, square_feet, city, property_type):
        """Generate a realistic apartment description"""
        
        bedroom_text = {
            0: 'studio',
            1: 'one bedroom',
            2: 'two bedroom',
            3: 'three bedroom',
            4: 'four bedroom',
        }.get(bedrooms, f'{bedrooms} bedroom')
        
        bathroom_text = f"{bathrooms} bathroom{'s' if bathrooms > 1 else ''}"
        
        descriptions = [
            f"<p>Welcome to this stunning {bedroom_text}, {bathroom_text} apartment located in the heart of {city}. "
            f"This beautiful {square_feet} sq ft property offers modern living at its finest.</p>"
            f"<p><strong>Property Highlights:</strong></p>"
            f"<ul>"
            f"<li>Spacious {square_feet} square feet of living space</li>"
            f"<li>{bedrooms} bedroom{'s' if bedrooms != 1 else ''} and {bathrooms} bathroom{'s' if bathrooms > 1 else ''}</li>"
            f"<li>Prime location in {city}</li>"
            f"<li>Modern finishes and appliances</li>"
            f"<li>Natural light throughout</li>"
            f"</ul>"
            f"<p>This apartment is perfect for professionals, families, or anyone looking for quality accommodation "
            f"in {city}. The unit features contemporary design with high-end finishes and is move-in ready.</p>"
            f"<p><strong>Neighborhood:</strong> Located in a vibrant area with easy access to shopping, dining, "
            f"entertainment, and public transportation. Enjoy the best that {city} has to offer right at your doorstep.</p>"
            f"<p>Don't miss this opportunity to make this beautiful apartment your new home!</p>",
            
            f"<p>Discover luxury living in this exquisite {property_type} situated in {city}'s most sought-after neighborhood. "
            f"With {square_feet} square feet of meticulously designed space, this {bedroom_text}, {bathroom_text} residence "
            f"sets a new standard for modern urban living.</p>"
            f"<p><strong>Features Include:</strong></p>"
            f"<ul>"
            f"<li>Open-concept floor plan with {square_feet} sq ft</li>"
            f"<li>Gourmet kitchen with premium appliances</li>"
            f"<li>Elegant hardwood floors throughout</li>"
            f"<li>Floor-to-ceiling windows with stunning views</li>"
            f"<li>In-unit washer and dryer</li>"
            f"</ul>"
            f"<p>The location offers unparalleled convenience with restaurants, shops, and entertainment options "
            f"just steps away. Public transportation is easily accessible, making your commute a breeze.</p>",
            
            f"<p>Experience the perfect blend of comfort and style in this remarkable {bedroom_text}, {bathroom_text} apartment. "
            f"Spanning {square_feet} square feet, this property in {city} offers everything you need for modern living.</p>"
            f"<p><strong>Key Features:</strong></p>"
            f"<ul>"
            f"<li>Bright and airy {square_feet} sq ft layout</li>"
            f"<li>Updated kitchen with stainless steel appliances</li>"
            f"<li>Spacious bedrooms with ample closet space</li>"
            f"<li>Modern bathroom{'s' if bathrooms > 1 else ''} with contemporary fixtures</li>"
            f"<li>Central heating and cooling</li>"
            f"</ul>"
            f"<p>Situated in a prime {city} location, you'll have easy access to all the amenities and attractions "
            f"the city has to offer. This is more than just an apartment – it's a lifestyle.</p>",
        ]
        
        return random.choice(descriptions)