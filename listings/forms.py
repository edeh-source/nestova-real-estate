from django import forms
from property.models import Property, PropertyImage
from ckeditor.widgets import CKEditorWidget

class PropertyForm(forms.ModelForm):
    secondary_images = forms.FileField(
        required=False,
        help_text='Upload multiple images (JPG, PNG, max 5MB each)'
    )
    
    class Meta:
        model = Property
        fields = [
            'title', 'state', 'city', 'address', 'zip_code',
            'property_type', 'status', 
            'bedrooms', 'bathrooms', 'square_feet', 'lot_size', 'year_built', 'parking_spaces',
            'price', 'description', 
            'has_garage', 'has_pool', 'has_garden', 'has_security', 'has_gym', 
            'has_balcony', 'is_furnished', 'has_ac', 'has_heating', 'pet_friendly',
            'featured_image', 'video_url', 'virtual_tour_url'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Property Title'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Address'}),
            'description': CKEditorWidget(config_name='default'),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'bathrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'square_feet': forms.NumberInput(attrs={'class': 'form-control'}),
            'state': forms.Select(attrs={'class': 'form-select'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'property_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
