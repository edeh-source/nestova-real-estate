import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page

from .models import CommunityEvent


@require_GET
@cache_page(60 * 15)           # cache 15 min — safe for homepage gallery
def events_json(request):
    """
    Lazy-loaded endpoint for the homepage events grid.
    Called by JS only after the section enters the viewport.
    """
    events = (
        CommunityEvent.objects
        .filter(is_active=True)
        .values('name', 'image', 'event_date', 'image_alt')
        .order_by('order', '-event_date')[:8]
    )

    payload = [
        {
            'name':  e['name'],
            'image': e['image'],          # relative path; prefix MEDIA_URL in JS
            'alt':   e['image_alt'] or e['name'],
            'date':  e['event_date'].strftime('%B %Y'),
        }
        for e in events
    ]

    return JsonResponse({'events': payload})