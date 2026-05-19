from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('api/events/', views.events_json, name='events-json'),
]