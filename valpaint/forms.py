from django import forms
from .models import ValpaintEnquiry


class ValpaintEnquiryForm(forms.ModelForm):
    class Meta:
        model  = ValpaintEnquiry
        fields = ('full_name', 'email', 'phone', 'location', 'quantity', 'message')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'vp-input',
                'placeholder': 'Your full name',
                'autocomplete': 'name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'vp-input',
                'placeholder': 'your@email.com',
                'autocomplete': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'vp-input',
                'placeholder': '+234 — optional',
                'autocomplete': 'tel',
            }),
            'location': forms.TextInput(attrs={
                'class': 'vp-input',
                'placeholder': 'City / area in Nigeria',
            }),
            'quantity': forms.TextInput(attrs={
                'class': 'vp-input',
                'placeholder': 'e.g. 10 tins, whole apartment',
            }),
            'message': forms.Textarea(attrs={
                'class': 'vp-input',
                'rows': 4,
                'placeholder': 'Tell us about your project…',
            }),
        }
        labels = {
            'full_name': 'Full Name',
            'phone':     'Phone (optional)',
            'location':  'Your Location',
            'quantity':  'Quantity / Scope',
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '')
        digits = ''.join(filter(str.isdigit, phone))
        if phone and len(digits) < 7:
            raise forms.ValidationError('Please enter a valid phone number.')
        return phone