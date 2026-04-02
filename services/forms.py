from django import forms
from .models import InteriorDesignRequest


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
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your full name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your.email@example.com'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+234 XXX XXX XXXX'
            }),
            'service_type': forms.Select(attrs={
                'class': 'form-select'
            }),
            'property_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter the full address of the property'
            }),
            'property_size': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2000 sq ft, 3 bedroom apartment'
            }),
            'budget_range': forms.Select(attrs={
                'class': 'form-select'
            }),
            'preferred_style': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Modern, Contemporary, Traditional, Minimalist'
            }),
            'project_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe your vision, requirements, and what you want to achieve with this project'
            }),
            'preferred_start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'project_deadline': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'reference_images': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf'
            }),
            'special_requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requirements or considerations (optional)'
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'service_type': 'Type of Service',
            'property_address': 'Property Address',
            'property_size': 'Property Size',
            'budget_range': 'Budget Range',
            'preferred_style': 'Preferred Design Style',
            'project_description': 'Project Description',
            'preferred_start_date': 'Preferred Start Date',
            'project_deadline': 'Project Deadline',
            'reference_images': 'Reference Images (Optional)',
            'special_requirements': 'Special Requirements (Optional)',
        }
