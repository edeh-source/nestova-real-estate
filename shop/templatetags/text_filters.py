# yourapp/templatetags/text_filters.py
from django import template
from django.utils.html import strip_tags
from django.utils.encoding import force_str
import re
import html

register = template.Library()

@register.filter
def clean_html(value):
    """
    Converts CKEditor HTML to clean, readable plain text.
    - Strips all tags
    - Decodes HTML entities (&mdash; → —, &rsquo; → ’, etc.)
    - Normalizes whitespace
    """
    if not value:
        return ""
    # 1. Strip HTML tags
    text = strip_tags(force_str(value))
    # 2. Decode HTML entities (e.g., &mdash; → —)
    text = html.unescape(text)
    # 3. Normalize whitespace: collapse newlines/tabs/spaces → single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text