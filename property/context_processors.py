from .models import PropertyType

def nav_property_types(request):
    """
    Inject active PropertyTypes into context for base.html navbar dropdowns (Buy & Rent).
    """
    try:
        types = PropertyType.objects.filter(is_active=True).order_by('display_order', 'name')
    except Exception:
        types = []
    return {
        'nav_property_types': types,
    }
