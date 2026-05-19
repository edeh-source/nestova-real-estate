import json
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from django.db.models import Count
from .models import CommunityEvent


@require_GET
@cache_page(1)
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


def all_events(request):
    qs = CommunityEvent.objects.filter(is_active=True).order_by('order', '-event_date')
 
    # ── Year filter ──────────────────────────────────────────
    active_year = request.GET.get('year')
    if active_year:
        try:
            active_year = int(active_year)
            qs = qs.filter(event_date__year=active_year)
        except (ValueError, TypeError):
            active_year = None
 
    # ── Sidebar year counts (always from the full active set) ─
    years = (
        CommunityEvent.objects
        .filter(is_active=True)
        .values('event_date__year')
        .annotate(count=Count('id'))
        .order_by('-event_date__year')
    )
 
    # Reshape for the template: [{year: 2025, count: 4}, ...]
    years = [
        {'year': y['event_date__year'], 'count': y['count']}
        for y in years
    ]
 
    # ── Total count (unfiltered) ─────────────────────────────
    total_count = CommunityEvent.objects.filter(is_active=True).count()
 
    # ── Year range stat (e.g. "2022 – 2025") ────────────────
    year_range = None
    if years:
        oldest = years[-1]['year']
        newest = years[0]['year']
        year_range = str(newest) if oldest == newest else f"{oldest}–{newest}"
 
    # ── Pagination — 12 per page (fills a 4-col grid neatly) ─
    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page', 1)
    events = paginator.get_page(page_number)
 
    context = {
        'events':      events,
        'years':       years,
        'active_year': active_year,
        'total_count': total_count,
        'year_range':  year_range,
    }
 
    return render(request, 'estate/all_events.html', context)