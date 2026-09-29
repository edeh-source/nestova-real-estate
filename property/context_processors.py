from django.core.cache import cache
from .models import PropertyType

def nav_property_types(request):
    """
    Inject active PropertyTypes into context for base.html navbar dropdowns (Buy & Rent).
    Cached for 10 minutes to avoid a DB hit on every request.
    """
    types = cache.get('nav_property_types')
    if types is None:
        try:
            types = list(PropertyType.objects.filter(is_active=True).order_by('display_order', 'name'))
        except Exception:
            types = []
        cache.set('nav_property_types', types, 600)
    return {'nav_property_types': types}
