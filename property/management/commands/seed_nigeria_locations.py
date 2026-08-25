"""
Management command: seed_nigeria_locations
------------------------------------------
Seeds all 36 Nigerian states and their major cities/districts
into the property_state and property_city tables.

Usage:
    python manage.py seed_nigeria_locations
"""

from django.core.management.base import BaseCommand
from property.nigeria_locations import seed_nigeria_locations


class Command(BaseCommand):
    help = "Seed Nigerian states and cities into the database from the built-in comprehensive dataset."

    def handle(self, *args, **options):
        self.stdout.write("Seeding Nigerian locations...")
        states_created, cities_created = seed_nigeria_locations()
        self.stdout.write(self.style.SUCCESS(
            f"Done! States created: {states_created}, Cities created: {cities_created}"
        ))
