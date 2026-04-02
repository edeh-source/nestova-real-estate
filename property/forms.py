from django import forms
from .models import PropertyApplication


class PropertyApplicationForm(forms.ModelForm):

    aml_accepted = forms.BooleanField(
        required=True,
        label=(
            "I confirm that the funds being used are not proceeds of crime and "
            "I agree to comply with all AML/CFT obligations as outlined above."
        ),
        error_messages={
            'required': 'You must accept the AML/CFT declaration to proceed.'
        }
    )

    class Meta:
        model = PropertyApplication
        exclude = [
            'listing', 'applicant', 'status',
            'admin_notes', 'submitted_at', 'updated_at'
        ]
        widgets = {
            # ── Personal ──────────────────────────────────────────────────
            'title':               forms.Select(attrs={'class': 'app-select'}),
            'surname':             forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Surname'}),
            'firstname':           forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'First Name'}),
            'other_names':         forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Other Names (optional)'}),
            'residential_address': forms.Textarea(attrs={'class': 'app-textarea', 'rows': 3, 'placeholder': 'Residential Address'}),
            'phone_number':        forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'e.g. 08012345678'}),
            'email':               forms.EmailInput(attrs={'class': 'app-input', 'placeholder': 'Email Address'}),
            'date_of_birth':       forms.DateInput(attrs={'class': 'app-input', 'type': 'date'}),
            'nationality':         forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'e.g. Nigerian'}),
            'marital_status':      forms.Select(attrs={'class': 'app-select'}),
            'occupation':          forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Occupation'}),
            'place_of_work':       forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Place of Work'}),
            'work_address':        forms.Textarea(attrs={'class': 'app-textarea', 'rows': 2, 'placeholder': 'Work Address'}),
            'passport_photo':      forms.FileInput(attrs={'class': 'app-file-input', 'accept': 'image/*'}),
            # id_type: rendered as custom radio pills in the template
            'id_type':             forms.RadioSelect(),
            'id_number':           forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'ID / Document Number'}),
            'id_document':         forms.FileInput(attrs={'class': 'app-file-input', 'accept': 'image/*,.pdf'}),
            'is_pep':              forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pep_details':         forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Name and position held'}),
            # ── Next of Kin ───────────────────────────────────────────────
            'nok_name':            forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Full Name'}),
            'nok_relationship':    forms.Select(attrs={'class': 'app-select'}),
            'nok_phone':           forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Phone Number'}),
            'nok_email':           forms.EmailInput(attrs={'class': 'app-input', 'placeholder': 'Email Address'}),
            'nok_address':         forms.Textarea(attrs={'class': 'app-textarea', 'rows': 2, 'placeholder': 'Address'}),
            # floor_choice & payment_plan: custom card UI writes to hidden inputs
            'floor_choice':        forms.HiddenInput(),
            'number_of_shops':     forms.NumberInput(attrs={'class': 'app-input', 'min': '1'}),
            'payment_plan':        forms.HiddenInput(),
            'intended_use':        forms.Textarea(attrs={'class': 'app-textarea', 'rows': 3, 'placeholder': 'e.g. retail store, office, service centre…'}),
            'subscriber_signature': forms.FileInput(attrs={'class': 'app-file-input', 'accept': 'image/*'}),
            'realtor_name':        forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Realtor / Agent Name'}),
            'realtor_email':       forms.EmailInput(attrs={'class': 'app-input', 'placeholder': 'Realtor Email'}),
            'realtor_phone':       forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'Realtor Phone'}),
            'realtor_cid':         forms.TextInput(attrs={'class': 'app-input', 'placeholder': 'CID Number'}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('is_pep') and not cleaned.get('pep_details', '').strip():
            self.add_error('pep_details', 'Please state the name and position of the PEP.')
        return cleaned