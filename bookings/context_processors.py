from django.core.cache import cache
from .models import ScrapedListing

def nav_cities(request):
    """Inject top cities into every template for the ShortLets nav dropdown."""
    cities = cache.get('nav_cities')
    if cities is None:
        cities_raw = (
            ScrapedListing.objects
            .exclude(city__isnull=True)
            .exclude(city='')
            .values_list('city', flat=True)
            .distinct()
        )
        seen = set()
        cities = []
        for c in cities_raw:
            normalized = c.strip().title()
            if normalized not in seen:
                seen.add(normalized)
                cities.append(normalized)
        cities = sorted(cities)
        cache.set('nav_cities', cities, 600)  # 10 minutes
    return {'nav_cities': cities}