from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import (
    InteriorDesignRequestForm,
    TourismInquiryForm,
    AcademyEnrollmentForm,
    BrokerageInquiryForm,
    BusinessPartnershipInquiryForm,
)
from .models import (
    InteriorDesignRequest,
    TourismInquiry,
    AcademyEnrollment,
    BrokerageInquiry,
    BusinessPartnershipInquiry,
)


# ==============================================================
#  MAIN ECOSYSTEM HUB — /services/
# ==============================================================

def all_services(request):
    """
    Main Nestova Ecosystem hub page showcasing all 4 pillars:
    Brokerage, Businesses, Academy, and Tourism.
    """
    return render(request, 'estate/services.html', {
        'page_title': 'The Nestova Ecosystem',
        'meta_description': (
            'Explore the Nestova Ecosystem — 4 powerful pillars: Brokerage, '
            'Businesses, Academy, and Tourism. One vision. Infinite possibilities.'
        ),
    })


# ==============================================================
#  BROKERAGE — /services/brokerage/
# ==============================================================

def brokerage(request):
    """
    Nestova Brokerage detail page — property sales, shortlets, interior design,
    SmartShield, industrial cleaning, and the realtor/developer hub.
    """
    if request.method == 'POST':
        form = BrokerageInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save(commit=False)
            if request.user.is_authenticated:
                inquiry.user = request.user
            inquiry.save()
            messages.success(
                request,
                'Thank you for your inquiry! Our brokerage team will contact you within 24 hours.'
            )
            return redirect('services:brokerage')
        else:
            messages.error(request, 'Please correct the errors below and resubmit.')
    else:
        form = BrokerageInquiryForm()
        if request.user.is_authenticated:
            form.initial = {
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
            }

    return render(request, 'services/brokerage.html', {
        'form': form,
        'page_title': 'Nestova Brokerage — Trusted Real Estate Solutions',
        'meta_description': (
            'Nestova Brokerage offers verified property sales, shortlet apartments, '
            'interior design, SmartShield security, industrial cleaning, and a realtor hub '
            'across Lagos, Abuja, Port Harcourt, Enugu and Owerri.'
        ),
    })


# ==============================================================
#  BUSINESSES — /services/businesses/
# ==============================================================

def businesses(request):
    """
    Nestova Businesses detail page — Valpaint, Communications, Essentials,
    SmartShield manufacturing, and Tourism partnerships.
    """
    if request.method == 'POST':
        form = BusinessPartnershipInquiryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                'Thank you for your partnership interest! Our business team will reach out within 48 hours.'
            )
            return redirect('services:businesses')
        else:
            messages.error(request, 'Please correct the errors below and resubmit.')
    else:
        form = BusinessPartnershipInquiryForm()

    return render(request, 'services/businesses.html', {
        'form': form,
        'page_title': 'Nestova Businesses — Lifestyle, Innovation & Smart Living',
        'meta_description': (
            'Nestova Businesses brings together Valpaint Italian luxury paints, '
            'Nestova Communications, Nestova Essentials, and SmartShield smart security '
            'into one powerful lifestyle and innovation ecosystem.'
        ),
    })


# ==============================================================
#  ACADEMY — /services/academy/
# ==============================================================

def academy(request):
    """
    Nestova Academy detail page — real estate training, entrepreneurship,
    mentorship, industry networking, and youth development.
    """
    if request.method == 'POST':
        form = AcademyEnrollmentForm(request.POST)
        if form.is_valid():
            enrollment = form.save(commit=False)
            if request.user.is_authenticated:
                enrollment.user = request.user
            enrollment.save()
            messages.success(
                request,
                'Your application has been received! We will review it and contact you within 48 hours.'
            )
            return redirect('services:academy')
        else:
            messages.error(request, 'Please correct the errors below and resubmit.')
    else:
        form = AcademyEnrollmentForm()
        if request.user.is_authenticated:
            form.initial = {
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
            }

    return render(request, 'services/academy.html', {
        'form': form,
        'page_title': 'Nestova Academy — Learning · Growth · Empowerment',
        'meta_description': (
            'Nestova Academy empowers individuals through real estate training, '
            'entrepreneurship development, business mentorship, industry networking, '
            'career empowerment, and youth development programs.'
        ),
    })


# ==============================================================
#  TOURISM — /services/tourism/
# ==============================================================

def tourism(request):
    """
    Nestova Tourism detail page — travel packages, hospitality partnerships,
    cultural tourism, investment opportunities, and youth empowerment.
    Powered by partnerships with PIP Foundation, NTDA, and TMD Foundation.
    """
    if request.method == 'POST':
        form = TourismInquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save(commit=False)
            if request.user.is_authenticated:
                inquiry.user = request.user
            inquiry.save()
            messages.success(
                request,
                'Thank you! Your tourism inquiry has been received. '
                'Our travel team will contact you within 24 hours to plan your experience.'
            )
            return redirect('services:tourism')
        else:
            messages.error(request, 'Please correct the errors below and resubmit.')
    else:
        form = TourismInquiryForm()
        if request.user.is_authenticated:
            form.initial = {
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
            }

    return render(request, 'services/tourism.html', {
        'form': form,
        'page_title': 'Nestova Tourism — Connecting People. Exploring Cultures. Creating Possibilities.',
        'meta_description': (
            'Nestova Tourism connects you to curated travel experiences, hospitality partnerships, '
            'cultural heritage tours, investment opportunities, and youth empowerment — '
            'across Nigeria, Africa, and the world.'
        ),
    })


# ==============================================================
#  INTERIOR DESIGN — /services/interior-design/ (existing)
# ==============================================================

def interior_design_request(request):
    """Handle interior design service requests"""
    if request.method == 'POST':
        form = InteriorDesignRequestForm(request.POST, request.FILES)
        if form.is_valid():
            design_request = form.save(commit=False)
            if request.user.is_authenticated:
                design_request.user = request.user
            design_request.save()
            messages.success(
                request,
                'Thank you for your interest in our interior design services! '
                'Our team will review your request and contact you within 24-48 hours.'
            )
            return redirect('services:interior_design_request')
        else:
            messages.error(
                request,
                'There was an error with your submission. Please check the form and try again.'
            )
    else:
        form = InteriorDesignRequestForm()
        if request.user.is_authenticated:
            form.initial = {
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
                'phone': getattr(request.user, 'phone', ''),
            }

    return render(request, 'services/interior_design_request.html', {'form': form})
