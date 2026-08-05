from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    # Main ecosystem hub
    path('', views.all_services, name='all_services'),

    # Ecosystem detail pages
    path('brokerage/', views.brokerage, name='brokerage'),
    path('businesses/', views.businesses, name='businesses'),
    path('academy/', views.academy, name='academy'),
    path('tourism/', views.tourism, name='tourism'),

    # Interior design (existing)
    path('interior-design/', views.interior_design_request, name='interior_design_request'),
]
