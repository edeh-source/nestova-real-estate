import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page

from .models import CommunityEvent


@require_GET
@cache_page(5)
def events_json(request):
    events = CommunityEvent.objects.filter(is_active=True).order_by('order', '-event_date')[:8]

    payload = [
        {
            'name':  e.name,
            'image': e.image.url if e.image else '',  # .url works in both environments
            'alt':   e.image_alt or e.name,
            'date':  e.event_date.strftime('%B %Y'),
        }
        for e in events
    ]

    return JsonResponse({'events': payload})