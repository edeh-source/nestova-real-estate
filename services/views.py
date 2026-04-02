from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import InteriorDesignRequestForm
from .models import InteriorDesignRequest


def all_services(request):
    """_summary_

    Args:
        request (_type_): _description_
    """
    services = InteriorDesignRequest.objects.all()
    return render(request, "estate/services.html", {"services": services})
    

def interior_design_request(request):
    """Handle interior design service requests"""
    if request.method == 'POST':
        form = InteriorDesignRequestForm(request.POST, request.FILES)
        if form.is_valid():
            design_request = form.save(commit=False)
            
            # Associate with logged-in user if available
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
        
        # Pre-fill user data if logged in
        if request.user.is_authenticated:
            form.initial = {
                'full_name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                'email': request.user.email,
                'phone': getattr(request.user, 'phone', ''),
            }
    
    context = {
        'form': form,
    }
    return render(request, 'services/interior_design_request.html', context)
