from django import forms
from property.models import Property, PropertyImage, State, City
from ckeditor.widgets import CKEditorWidget

class PropertyForm(forms.ModelForm):
    city = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Awka, Onitsha, Nnewi, Lekki, Maitama, Wuse 2'
        }),
        help_text='Type the city, town, or neighborhood'
    )
    secondary_images = forms.FileField(
        required=False,
        help_text='Upload multiple images (JPG, PNG, max 5MB each)'
    )
    
    class Meta:
        model = Property
        fields = [
            'title', 'state', 'address', 'zip_code',
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
            'property_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.city:
            self.fields['city'].initial = self.instance.city.name

    def clean_city(self):
        city_name = self.cleaned_data.get('city', '').strip()
        if not city_name:
            raise forms.ValidationError("Please enter a city or area name.")
        return city_name.title()

    def save(self, commit=True):
        instance = super().save(commit=False)
        city_name = self.cleaned_data.get('city')
        state = self.cleaned_data.get('state')
        if city_name and state:
            city_obj = City.objects.filter(name__iexact=city_name, state=state).first()
            if not city_obj:
                city_obj = City.objects.create(name=city_name, state=state, is_active=True)
            instance.city = city_obj
        if commit:
            instance.save()
            self.save_m2m()
        return instance
