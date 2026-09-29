from django.core.cache import cache
from .models import ContactInfo

def contact_info(request):
    """
    Context processor to make ContactInfo available to all templates.
    Cached for 10 minutes to avoid a DB hit on every request.
    """
    info = cache.get('contact_info_active')
    if info is None:
        info = ContactInfo.get_active()
        cache.set('contact_info_active', info, 600)
    return {'contact_info': info}
