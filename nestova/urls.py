"""
URL configuration for nestova project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from core.sitemaps import PropertySitemap, ProductSitemap, BlogSitemap, StaticPagesSitemap

# Sitemap configuration
sitemaps = {
    'properties': PropertySitemap,
    'products': ProductSitemap,
    'blog': BlogSitemap,
    'static': StaticPagesSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # SEO URLs
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots_seo.txt', content_type='text/plain'), name='robots_txt'),
    
    # IMPORTANT: Custom auth URLs MUST come BEFORE allauth to prevent override
    path("", include("users.urls")),  # Custom login/register at /login/ and /register/
    
    # App URLs
    path("", include("core.urls")),
    path('booking/', include('bookings.urls')),
    path("agents/", include("agents.urls")),  # Agent URLs with prefix
    path("", include("property.urls")),
    path('shop/', include('shop.urls')),
    path('listings/', include('listings.urls')),
    path('blog/', include('blogs.urls')),
    path('services/', include('services.urls')),
    path('', include("contact.urls")),
    
    # Allauth URLs (for social auth only - login/register handled by custom views)
    path('accounts/', include('allauth.urls')),
]

# Custom error handlers
handler404 = 'nestova.views.custom_404'
handler500 = 'nestova.views.custom_500'


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)