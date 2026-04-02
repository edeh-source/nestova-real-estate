from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.all_services, name='all_services'),
    path('interior-design/', views.interior_design_request, name='interior_design_request'),
    
]
