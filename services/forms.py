from django import forms
from .models import (
    InteriorDesignRequest,
    TourismInquiry,
    AcademyEnrollment,
    BrokerageInquiry,
    BusinessPartnershipInquiry,
)

# ── Common widget kwargs ────────────────────────────────────────────────────────
_TEXT   = lambda ph: forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph})
_EMAIL  = lambda ph: forms.EmailInput(attrs={'class': 'form-control', 'placeholder': ph})
_TEL    = lambda ph: forms.TextInput(attrs={'class': 'form-control', 'placeholder': ph})
_SELECT = lambda: forms.Select(attrs={'class': 'form-select'})
_AREA   = lambda ph, rows=4: forms.Textarea(attrs={'class': 'form-control', 'placeholder': ph, 'rows': rows})
_DATE   = lambda: forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
_NUM    = lambda ph: forms.NumberInput(attrs={'class': 'form-control', 'placeholder': ph})


# ==============================================================
#  EXISTING FORM — Interior Design Request
# ==============================================================

class InteriorDesignRequestForm(forms.ModelForm):
    """Form for submitting interior design service requests"""

    class Meta:
        model = InteriorDesignRequest
        fields = [
            'full_name', 'email', 'phone', 'service_type',
            'property_address', 'property_size', 'budget_range',
            'preferred_style', 'project_description',
            'preferred_start_date', 'project_deadline',
            'reference_images', 'special_requirements'
        ]
        widgets = {
            'full_name':            _TEXT('Enter your full name'),
            'email':                _EMAIL('your.email@example.com'),
            'phone':                _TEL('+234 XXX XXX XXXX'),
            'service_type':         _SELECT(),
            'property_address':     _AREA('Enter the full address of the property', 3),
            'property_size':        _TEXT('e.g., 2000 sq ft, 3 bedroom apartment'),
            'budget_range':         _SELECT(),
            'preferred_style':      _TEXT('e.g., Modern, Contemporary, Traditional, Minimalist'),
            'project_description':  _AREA('Describe your vision, requirements, and what you want to achieve', 5),
            'preferred_start_date': _DATE(),
            'project_deadline':     _DATE(),
            'reference_images':     forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'special_requirements': _AREA('Any special requirements or considerations (optional)', 3),
        }
        labels = {
            'full_name':            'Full Name',
            'email':                'Email Address',
            'phone':                'Phone Number',
            'service_type':         'Type of Service',
            'property_address':     'Property Address',
            'property_size':        'Property Size',
            'budget_range':         'Budget Range',
            'preferred_style':      'Preferred Design Style',
            'project_description':  'Project Description',
            'preferred_start_date': 'Preferred Start Date',
            'project_deadline':     'Project Deadline',
            'reference_images':     'Reference Images (Optional)',
            'special_requirements': 'Special Requirements (Optional)',
        }


# ==============================================================
#  TOURISM — Inquiry Form
# ==============================================================

class TourismInquiryForm(forms.ModelForm):
    """Form for trip planning and tourism partnership inquiries"""

    class Meta:
        model = TourismInquiry
        fields = [
            'full_name', 'email', 'phone',
            'inquiry_type', 'destination_preference',
            'group_size', 'budget_range',
            'preferred_travel_date', 'trip_duration',
            'special_interests', 'message',
        ]
        widgets = {
            'full_name':              _TEXT('Enter your full name'),
            'email':                  _EMAIL('your.email@example.com'),
            'phone':                  _TEL('+234 XXX XXX XXXX'),
            'inquiry_type':           _SELECT(),
            'destination_preference': _SELECT(),
            'group_size':             _SELECT(),
            'budget_range':           _SELECT(),
            'preferred_travel_date':  _DATE(),
            'trip_duration':          _TEXT('e.g., 3 days, 1 week, 2 weeks'),
            'special_interests':      _TEXT('e.g., history, beaches, food, adventure, culture'),
            'message':                _AREA('Tell us about your dream experience or what you\'re looking for…', 5),
        }
        labels = {
            'full_name':              'Full Name',
            'email':                  'Email Address',
            'phone':                  'Phone Number',
            'inquiry_type':           'Type of Inquiry',
            'destination_preference': 'Destination Preference',
            'group_size':             'Group Size',
            'budget_range':           'Budget Range',
            'preferred_travel_date':  'Preferred Travel Date (Optional)',
            'trip_duration':          'Trip Duration (Optional)',
            'special_interests':      'Special Interests (Optional)',
            'message':                'Tell Us More',
        }


# ==============================================================
#  ACADEMY — Enrollment Form
# ==============================================================

class AcademyEnrollmentForm(forms.ModelForm):
    """Form for registering into Nestova Academy programs"""

    class Meta:
        model = AcademyEnrollment
        fields = [
            'full_name', 'email', 'phone', 'age', 'occupation', 'location',
            'program', 'experience_level', 'preferred_format',
            'goals', 'how_heard', 'referral_name',
        ]
        widgets = {
            'full_name':        _TEXT('Enter your full name'),
            'email':            _EMAIL('your.email@example.com'),
            'phone':            _TEL('+234 XXX XXX XXXX'),
            'age':              _NUM('Your age'),
            'occupation':       _TEXT('e.g., Real Estate Agent, Entrepreneur, Student'),
            'location':         _TEXT('e.g., Lagos, Abuja, Port Harcourt'),
            'program':          _SELECT(),
            'experience_level': _SELECT(),
            'preferred_format': _SELECT(),
            'goals':            _AREA('What do you hope to achieve from this program? Be specific.', 5),
            'how_heard':        _TEXT('e.g., Instagram, Referral, WhatsApp, Google'),
            'referral_name':    _TEXT('Full name of the person who referred you (optional)'),
        }
        labels = {
            'full_name':        'Full Name',
            'email':            'Email Address',
            'phone':            'Phone Number',
            'age':              'Age',
            'occupation':       'Current Occupation',
            'location':         'City / State of Residence',
            'program':          'Program of Interest',
            'experience_level': 'Experience Level',
            'preferred_format': 'Preferred Learning Format',
            'goals':            'Your Goals & Motivation',
            'how_heard':        'How Did You Hear About Us?',
            'referral_name':    'Referred By (Optional)',
        }


# ==============================================================
#  BROKERAGE — General Service Inquiry Form
# ==============================================================

class BrokerageInquiryForm(forms.ModelForm):
    """Form for brokerage service inquiries (property, shortlets, cleaning, security, etc.)"""

    class Meta:
        model = BrokerageInquiry
        fields = [
            'full_name', 'email', 'phone',
            'service_requested', 'location', 'timeline', 'budget', 'message',
        ]
        widgets = {
            'full_name':         _TEXT('Enter your full name'),
            'email':             _EMAIL('your.email@example.com'),
            'phone':             _TEL('+234 XXX XXX XXXX'),
            'service_requested': _SELECT(),
            'location':          _SELECT(),
            'timeline':          _SELECT(),
            'budget':            _TEXT('e.g., ₦5,000,000 – ₦10,000,000'),
            'message':           _AREA('Describe what you need — the more detail, the better we can help you.', 5),
        }
        labels = {
            'full_name':         'Full Name',
            'email':             'Email Address',
            'phone':             'Phone Number',
            'service_requested': 'Service Required',
            'location':          'Location / State',
            'timeline':          'Timeline',
            'budget':            'Budget Range (Optional)',
            'message':           'Additional Details',
        }


# ==============================================================
#  BUSINESSES — Partnership Inquiry Form
# ==============================================================

class BusinessPartnershipInquiryForm(forms.ModelForm):
    """Form for partnership and collaboration inquiries with Nestova Businesses"""

    class Meta:
        model = BusinessPartnershipInquiry
        fields = [
            'full_name', 'business_name', 'email', 'phone',
            'location', 'website', 'partnership_type', 'business_size', 'message',
        ]
        widgets = {
            'full_name':        _TEXT('Your full name'),
            'business_name':    _TEXT('Business / company name (if applicable)'),
            'email':            _EMAIL('your.email@example.com'),
            'phone':            _TEL('+234 XXX XXX XXXX'),
            'location':         _TEXT('City, State / Country'),
            'website':          forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://yourbusiness.com (optional)'}),
            'partnership_type': _SELECT(),
            'business_size':    _SELECT(),
            'message':          _AREA('Describe your proposal — what you offer and how we can collaborate.', 5),
        }
        labels = {
            'full_name':        'Contact Person',
            'business_name':    'Business Name (Optional)',
            'email':            'Email Address',
            'phone':            'Phone Number',
            'location':         'Location',
            'website':          'Website (Optional)',
            'partnership_type': 'Type of Partnership',
            'business_size':    'Business Size',
            'message':          'Your Proposal',
        }
