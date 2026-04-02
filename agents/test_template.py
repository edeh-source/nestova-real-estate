import os
import sys
import django
from django.conf import settings
from django.template import Template, Context, loader

# Initialise Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nestova.settings')
django.setup()

try:
    t = loader.get_template('includes/seo_meta.html')
    print("Template loaded successfully!")
    rendered = t.render({})
    print("Template rendered successfully (with empty context)!")
    print("Rendered content length:", len(rendered))
except Exception as e:
    print(f"Error: {e}")
