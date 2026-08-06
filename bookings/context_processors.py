# booking/context_processors.py

from .models import ScrapedListing

def nav_cities(request):
    """Inject top cities into every template for the ShortLets nav dropdown."""
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

    return {'nav_cities': sorted(cities)}