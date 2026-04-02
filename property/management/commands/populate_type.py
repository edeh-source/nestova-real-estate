# management/commands/populate_property_types.py
from django.core.management.base import BaseCommand
from property.models import PropertyType

class Command(BaseCommand):
    help = 'Populate property types'

    def handle(self, *args, **kwargs):
        property_types = [
            # Residential
            {'name': 'detached_house', 'category': 'residential', 'icon': 'bi bi-house-door', 'order': 1},
            {'name': 'semi_detached', 'category': 'residential', 'icon': 'bi bi-house', 'order': 2},
            {'name': 'terrace', 'category': 'residential', 'icon': 'bi bi-buildings', 'order': 3},
            {'name': 'duplex', 'category': 'residential', 'icon': 'bi bi-building', 'order': 4},
            {'name': 'bungalow', 'category': 'residential', 'icon': 'bi bi-house-door-fill', 'order': 5},
            {'name': 'mansion', 'category': 'residential', 'icon': 'bi bi-house-heart', 'order': 6},
            {'name': 'villa', 'category': 'residential', 'icon': 'bi bi-house-fill', 'order': 7},
            
            # Apartments
            {'name': 'studio', 'category': 'residential', 'icon': 'bi bi-door-open', 'order': 10},
            {'name': '1_bed_flat', 'category': 'residential', 'icon': 'bi bi-door-open', 'order': 11},
            {'name': '2_bed_flat', 'category': 'residential', 'icon': 'bi bi-door-open', 'order': 12},
            {'name': '3_bed_flat', 'category': 'residential', 'icon': 'bi bi-door-open', 'order': 13},
            {'name': 'penthouse', 'category': 'residential', 'icon': 'bi bi-building-up', 'order': 14},
            
            # Nigerian Specific
            {'name': 'self_contain', 'category': 'residential', 'icon': 'bi bi-house-door', 'order': 20},
            {'name': 'room_parlour', 'category': 'residential', 'icon': 'bi bi-door-open', 'order': 21},
            {'name': 'mini_flat', 'category': 'residential', 'icon': 'bi bi-door-closed', 'order': 22},
            {'name': 'boys_quarters', 'category': 'residential', 'icon': 'bi bi-house-door', 'order': 23},
            
            # Commercial
            {'name': 'office', 'category': 'commercial', 'icon': 'bi bi-briefcase', 'order': 30},
            {'name': 'shop', 'category': 'commercial', 'icon': 'bi bi-shop', 'order': 31},
            {'name': 'mall', 'category': 'commercial', 'icon': 'bi bi-shop-window', 'order': 32},
            {'name': 'warehouse', 'category': 'commercial', 'icon': 'bi bi-box-seam', 'order': 33},
            {'name': 'hotel', 'category': 'commercial', 'icon': 'bi bi-building', 'order': 34},
            {'name': 'filling_station', 'category': 'commercial', 'icon': 'bi bi-fuel-pump', 'order': 35},
            
            # Land
            {'name': 'residential_land', 'category': 'land', 'icon': 'bi bi-geo', 'order': 40},
            {'name': 'commercial_land', 'category': 'land', 'icon': 'bi bi-geo-alt', 'order': 41},
            {'name': 'agricultural_land', 'category': 'land', 'icon': 'bi bi-tree', 'order': 42},
            
            # Special
            {'name': 'compound', 'category': 'special', 'icon': 'bi bi-houses', 'order': 50},
            {'name': 'estate_house', 'category': 'special', 'icon': 'bi bi-house-check', 'order': 51},
        ]
        
        created = 0
        for pt in property_types:
            obj, created_flag = PropertyType.objects.get_or_create(
                name=pt['name'],
                defaults={
                    'category': pt['category'],
                    'icon': pt['icon'],
                    'display_order': pt['order']
                }
            )
            if created_flag:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {obj.get_name_display()}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully populated {created} property types!'))