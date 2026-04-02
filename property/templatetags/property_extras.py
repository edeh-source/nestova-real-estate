from django import template
import re

register = template.Library()

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()

@register.filter(name='force_https')
def force_https(url):
    """Force URL to use HTTPS"""
    if url and url.startswith('http://'):
        return url.replace('http://', 'https://')
    return url

@register.filter(name='youtube_id')
def youtube_id(value):
    """Extract YouTube ID from URL. Returns None if no ID found."""
    if not value:
        return None
    
    # If the value is a field object, get the URL string
    val_str = str(value.url if hasattr(value, 'url') else value).strip()

    # Improved Regex to handle: 
    # watch?v=ID, youtu.be/ID, embed/ID, shorts/ID, and ?si= tracking params
    yt_pattern = r'(?:v=|/v/|/embed/|youtu\.be/|/shorts/|^)([a-zA-Z0-9_-]{11})(?:[?&]|$)'
    
    match = re.search(yt_pattern, val_str)
    if match:
        return match.group(1)
    
    # Check if the string itself is just an 11-char ID
    if len(val_str) == 11 and re.match(r'^[a-zA-Z0-9_-]{11}$', val_str):
        return val_str
        
    return None