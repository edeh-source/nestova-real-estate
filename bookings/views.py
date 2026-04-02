from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from .models import Apartment, Booking, Review, Payment, ApartmentImage, ApartmentChoice
import json


def apartment_list(request):
    """Display list of available apartments with filters"""
    apartments = Apartment.objects.filter(status='available')
    
    # Filters
    property_type = request.GET.get('property_type')
    city = request.GET.get('city')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    search = request.GET.get('search')
    
    # Apply filters
    if property_type:
        apartments = apartments.filter(property_type=property_type)
    if city:
        apartments = apartments.filter(city__icontains=city)
    if min_price:
        apartments = apartments.filter(price_per_night__gte=min_price)
    if max_price:
        apartments = apartments.filter(price_per_night__lte=max_price)
    if bedrooms:
        apartments = apartments.filter(bedrooms__gte=bedrooms)
    if bathrooms:
        apartments = apartments.filter(bathrooms__gte=bathrooms)
    if search:
        apartments = apartments.filter(
            Q(title__icontains=search) | 
            Q(description__icontains=search) |
            Q(city__icontains=search) |
            Q(address__icontains=search)
        )
    
    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_low':
        apartments = apartments.order_by('price_per_night')
    elif sort_by == 'price_high':
        apartments = apartments.order_by('-price_per_night')
    elif sort_by == 'newest':
        apartments = apartments.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(apartments, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique cities for filter
    cities = Apartment.objects.values_list('city', flat=True).distinct()
    apartmentchoice = ApartmentChoice.objects.values_list('name', flat=True).distinct()
    
    context = {
        'apartments': page_obj,
        'cities': cities,
        'apartmentchoice': apartmentchoice
    }
    
    return render(request, 'booking/apartment_list.html', context)


def apartment_detail(request, slug):
    """Display detailed information about an apartment"""
    apartment = get_object_or_404(Apartment, slug=slug)
    
    # Get reviews with average ratings
    reviews = apartment.reviews.all()[:5]
    avg_ratings = apartment.reviews.aggregate(
        avg_overall=Avg('overall_rating'),
        avg_cleanliness=Avg('cleanliness_rating'),
        avg_communication=Avg('communication_rating'),
        avg_location=Avg('location_rating'),
        avg_value=Avg('value_rating'),
        total_reviews=Count('id')
    )
    
    # Get additional images
    images = apartment.images.all()
    
    # Check availability for next 30 days
    today = timezone.now().date()
    bookings = apartment.bookings.filter(
        check_in_date__gte=today,
        booking_status__in=['confirmed', 'checked_in']
    ).order_by('check_in_date')
    
    context = {
        'apartment': apartment,
        'reviews': reviews,
        'avg_ratings': avg_ratings,
        'images': images,
        'upcoming_bookings': bookings,
        'amenities': apartment.get_amenities_list(),
    }
    
    return render(request, 'booking/apartment_detail.html', context)


@login_required
def create_booking(request, apartment_id):
    """Create a new booking for an apartment"""
    apartment = get_object_or_404(Apartment, pk=apartment_id)
    
    if request.method == 'POST':
        try:
            # Get form data
            check_in = datetime.strptime(request.POST.get('check_in_date'), '%Y-%m-%d').date()
            check_out = datetime.strptime(request.POST.get('check_out_date'), '%Y-%m-%d').date()
            number_of_guests = int(request.POST.get('number_of_guests'))
            
            # Validate dates
            today = timezone.now().date()
            if check_in < today:
                messages.error(request, 'Check-in date cannot be in the past.')
                return redirect('apartment_detail', pk=apartment_id)
            
            if check_out <= check_in:
                messages.error(request, 'Check-out date must be after check-in date.')
                return redirect('apartment_detail', pk=apartment_id)
            
            if number_of_guests > apartment.max_guests:
                messages.error(request, f'Maximum guests allowed: {apartment.max_guests}')
                return redirect('apartment_detail', pk=apartment_id)
            
            # Check for overlapping bookings
            overlapping = apartment.bookings.filter(
                Q(check_in_date__lte=check_out) & Q(check_out_date__gte=check_in),
                booking_status__in=['confirmed', 'checked_in']
            ).exists()
            
            if overlapping:
                messages.error(request, 'This apartment is not available for the selected dates.')
                return redirect('apartment_detail', pk=apartment_id)
            
            # Create booking
            booking = Booking.objects.create(
                apartment=apartment,
                user=request.user,
                check_in_date=check_in,
                check_out_date=check_out,
                number_of_guests=number_of_guests,
                guest_name=request.POST.get('guest_name', f"{request.user.first_name} {request.user.last_name}"),
                guest_email=request.POST.get('guest_email', request.user.email),
                guest_phone=request.POST.get('guest_phone'),
                special_requests=request.POST.get('special_requests', ''),
                security_deposit_paid=apartment.security_deposit
            )
            
            messages.success(request, f'Booking created successfully! Booking number: {booking.booking_number}')
            return redirect('booking_confirmation', booking_id=booking.id)
            
        except Exception as e:
            messages.error(request, f'Error creating booking: {str(e)}')
            return redirect('apartment_detail', pk=apartment_id)
    
    return redirect('apartment_detail', pk=apartment_id)


@login_required
def booking_confirmation(request, booking_id):
    """Display booking confirmation page"""
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    
    context = {
        'booking': booking,
    }
    
    return render(request, 'booking/booking_confirmation.html', context)


@login_required
def my_bookings(request):
    """Display user's bookings"""
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        bookings = bookings.filter(booking_status=status_filter)
    
    # Pagination
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'bookings': page_obj,
        'status_choices': Booking.BOOKING_STATUS_CHOICES,
    }
    
    return render(request, 'booking/my_bookings.html', context)


@login_required
def booking_detail(request, booking_id):
    """Display detailed booking information"""
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    
    # Get payment history
    payments = booking.payments.all()
    
    context = {
        'booking': booking,
        'payments': payments,
    }
    
    return render(request, 'booking/booking_detail.html', context)


@login_required
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    
    if request.method == 'POST':
        if booking.can_cancel():
            booking.booking_status = 'cancelled'
            booking.save()
            messages.success(request, 'Booking cancelled successfully.')
        else:
            messages.error(request, 'This booking cannot be cancelled.')
    
    return redirect('my_bookings')


@login_required
def create_review(request, booking_id):
    """Create a review for a completed booking"""
    booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
    
    # Check if booking is completed
    if booking.booking_status != 'checked_out':
        messages.error(request, 'You can only review completed bookings.')
        return redirect('booking_detail', booking_id=booking_id)
    
    # Check if review already exists
    if hasattr(booking, 'review'):
        messages.error(request, 'You have already reviewed this booking.')
        return redirect('booking_detail', booking_id=booking_id)
    
    if request.method == 'POST':
        try:
            review = Review.objects.create(
                booking=booking,
                apartment=booking.apartment,
                user=request.user,
                overall_rating=int(request.POST.get('overall_rating')),
                cleanliness_rating=int(request.POST.get('cleanliness_rating')),
                communication_rating=int(request.POST.get('communication_rating')),
                location_rating=int(request.POST.get('location_rating')),
                value_rating=int(request.POST.get('value_rating')),
                title=request.POST.get('title'),
                comment=request.POST.get('comment')
            )
            messages.success(request, 'Review submitted successfully!')
            return redirect('apartment_detail', pk=booking.apartment.id)
        except Exception as e:
            messages.error(request, f'Error submitting review: {str(e)}')
    
    context = {
        'booking': booking,
    }
    
    return render(request, 'booking/create_review.html', context)


@login_required
def check_availability(request):
    """AJAX endpoint to check apartment availability"""
    if request.method == 'GET':
        apartment_id = request.GET.get('apartment_id')
        check_in = request.GET.get('check_in')
        check_out = request.GET.get('check_out')
        
        try:
            apartment = Apartment.objects.get(pk=apartment_id)
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            # Check for overlapping bookings
            overlapping = apartment.bookings.filter(
                Q(check_in_date__lte=check_out_date) & Q(check_out_date__gte=check_in_date),
                booking_status__in=['confirmed', 'checked_in']
            ).exists()
            
            # Calculate price
            nights = (check_out_date - check_in_date).days
            total_price = apartment.price_per_night * nights
            
            return JsonResponse({
                'available': not overlapping,
                'nights': nights,
                'price_per_night': float(apartment.price_per_night),
                'total_price': float(total_price),
                'security_deposit': float(apartment.security_deposit)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)