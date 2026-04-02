from django.urls import path
from . import views

urlpatterns = [
    # Apartment URLs
    path('', views.apartment_list, name='apartment_list'),
    path('apartment/<slug:slug>/', views.apartment_detail, name='apartment_details'),
    
    # Booking URLs
    path('apartment/<int:apartment_id>/book/', views.create_booking, name='create_booking'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('booking/<int:booking_id>/confirmation/', views.booking_confirmation, name='booking_confirmation'),
    path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    # Review URLs
    path('booking/<int:booking_id>/review/', views.create_review, name='create_review'),
    
    # AJAX URLs
    path('api/check-availability/', views.check_availability, name='check_availability'),
]

