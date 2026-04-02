from .models import ContactInfo


def contact_info(request):
    """
    Context processor to make ContactInfo available to all templates.
    This ensures that contact information is accessible globally without
    needing to pass it explicitly in every view.
    """
    contact_info_instance = ContactInfo.get_active()
    return {
        'contact_info': contact_info_instance
    }
