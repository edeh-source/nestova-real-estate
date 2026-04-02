"""
Sitemaps for SEO - Helps search engines discover and index content
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from property.models import Property
from shop.models import Product
from blogs.models import Post


class PropertySitemap(Sitemap):
    """Sitemap for property listings"""
    changefreq = "daily"
    priority = 0.9
    
    def items(self):
        return Property.objects.filter(is_active=True).select_related('city', 'state')
    
    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else obj.created_at
    
    def location(self, obj):
        return f'/property/{obj.slug}/'


class ProductSitemap(Sitemap):
    """Sitemap for shop products"""
    changefreq = "weekly"
    priority = 0.8
    
    def items(self):
        return Product.objects.filter(is_available=True).select_related('category')
    
    def lastmod(self, obj):
        return obj.updated_at if hasattr(obj, 'updated_at') else obj.created_at
    
    def location(self, obj):
        return f'/shop/product/{obj.slug}/'


class BlogSitemap(Sitemap):
    """Sitemap for blog posts"""
    changefreq = "monthly"
    priority = 0.7
    
    def items(self):
        return Post.objects.filter(status='published').select_related('author', 'category')
    
    def lastmod(self, obj):
        return obj.updated if hasattr(obj, 'updated') else obj.publish
    
    def location(self, obj):
        return f'/blog/{obj.publish.year}/{obj.publish.month}/{obj.publish.day}/{obj.slug}/'


class StaticPagesSitemap(Sitemap):
    """Sitemap for static pages"""
    changefreq = "monthly"
    priority = 0.6
    
    def items(self):
        return [
            'home',
            'about',
            'contact',
            'service',
            'properties',
            'agents',
            'post_list',
            'shop:product_list',
            'apartment_list',
        ]
    
    def location(self, item):
        return reverse(item)
