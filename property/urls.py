# urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Homepage
    path('', views.homepage, name='home'),
    
    # AJAX endpoint for cities
    path('api/get-cities/', views.get_cities_by_state, name='get_cities_by_state'),
    path("properties/", views.property_list, name="properties"),
    path('property/details/<slug:slug>/', views.get_properties_details, name='property_detail'),
    
    # Property search
    path('properties/search/', views.search_properties, name='search_properties'),
    
]