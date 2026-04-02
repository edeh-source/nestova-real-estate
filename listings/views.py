from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import ListingPackage, UserSubscription
from .forms import PropertyForm
from property.models import Property, PropertyImage
from django.db.models import Count
from django.conf import settings
from django.urls import reverse
import random
import requests




@login_required
def dashboard(request):
    """
    User dashboard showing active listings and slot usage.
    """
    sub, created = UserSubscription.objects.get_or_create(user=request.user)
    
    # If no package assigned, check if there's a default free package
    if not sub.package:
        default_pkg = ListingPackage.objects.filter(is_default=True).first()
        if default_pkg:
            sub.package = default_pkg
            sub.save()
            messages.info(request, f"You've been assigned the {default_pkg.name} starter package.")

    user_properties = Property.objects.filter(listed_by=request.user).order_by('-created_at')
    
    context = {
        'subscription': sub,
        'properties': user_properties,
        'used_slots': sub.get_used_slots(),
        'remaining_slots': sub.remaining_slots if sub.package else 0,
        'has_package': sub.package is not None
    }
    return render(request, 'listings/dashboard.html', context)

@login_required
def post_property(request):
    """
    View to post a new property. Checks for available slots.
    """
    sub, created = UserSubscription.objects.get_or_create(user=request.user)
    
    # Check if user has remaining slots
    if not sub.has_remaining_slots():
        messages.warning(
            request, 
            f"You have used all {sub.total_slots} of your slots. Please purchase more slots to post additional properties."
        )
        return redirect('listings:pricing')
    
    # Enforce Mandatory Verification
    if hasattr(request.user, 'agent_profile'):
        agent = request.user.agent_profile
        if not agent.can_post_properties:
            messages.warning(request, "Your account must be verified before you can post properties.")
            return redirect('agents:verification_dashboard')
    elif hasattr(request.user, 'company_profile'):
        company = request.user.company_profile
        if not company.can_post_properties:
            messages.warning(request, "Your company account must be verified before you can post properties.")
            return redirect('agents:verification_dashboard')
    else:
        # Normal users must also verify before posting
        if not request.user.id_verified or not request.user.can_post_properties:
            messages.warning(request, "You must verify your identity before posting properties.")
            return redirect('users:submit_user_verification')

    
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            property_obj = form.save(commit=False)
            property_obj.listed_by = request.user
            property_obj.save()
            
            # Handle secondary images
            images = request.FILES.getlist('secondary_images')
            for idx, image in enumerate(images):
                PropertyImage.objects.create(
                    property=property_obj,
                    image=image,
                    is_primary=False,
                    order=idx
                )
            
            # Increment used slots
            sub.use_slot()
            
            messages.success(
                request, 
                f"Property posted successfully! You have {sub.remaining_slots} slots remaining."
            )
            return redirect('shop:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PropertyForm()
    
    # Pass remaining slots to template
    context = {
        'form': form,
        'remaining_slots': sub.remaining_slots,
        'total_slots': sub.total_slots,
        'used_slots': sub.used_slots,
        'is_edit': False,
    }
    return render(request, 'listings/post_property.html', context)


@login_required
def edit_property(request, slug):
    """
    View to edit an existing property.
    """
    property_obj = get_object_or_404(Property, slug=slug)
    
    # Ensure only the owner can edit
    if property_obj.listed_by != request.user:
        messages.error(request, "You don't have permission to edit this property.")
        return redirect('shop:profile')
    
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property_obj)
        if form.is_valid():
            property_obj = form.save(commit=False)
            property_obj.save()
            
            # Handle secondary images
            images = request.FILES.getlist('secondary_images')
            if images:
                # Add new images
                for idx, image in enumerate(images):
                    # Get the current max order
                    max_order = PropertyImage.objects.filter(property=property_obj).count()
                    PropertyImage.objects.create(
                        property=property_obj,
                        image=image,
                        is_primary=False,
                        order=max_order + idx
                    )
            
            messages.success(request, "Property updated successfully!")
            return redirect('shop:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PropertyForm(instance=property_obj)
    
    # Get existing secondary images
    existing_images = PropertyImage.objects.filter(property=property_obj, is_primary=False).order_by('order')
    
    context = {
        'form': form,
        'property': property_obj,
        'existing_images': existing_images,
        'is_edit': True,
    }
    return render(request, 'listings/post_property.html', context)


def pricing_plans(request):
    """
    Show available slot packages for purchase.
    """
    packages = ListingPackage.objects.filter(is_active=True).order_by('price')
    
    # Get user's current slot status if logged in
    user_subscription = None
    if request.user.is_authenticated:
        user_subscription, _ = UserSubscription.objects.get_or_create(user=request.user)
    
    context = {
        'packages': packages,
        'user_subscription': user_subscription,
    }
    return render(request, 'listings/pricing.html', context)


def subscribe(request, package_id):
    """
    Handle slot package purchase.
    In production, integrate Payment Gateway here (Paystack/Flutterwave).
    For now, simple slot addition for testing.
    """
    if not request.user.is_authenticated:
        return redirect("users:login")
    
    pkg = get_object_or_404(ListingPackage, id=package_id)
    
    # Get or create user subscription
    sub, created = UserSubscription.objects.get_or_create(user=request.user)
    
    # TODO: In production, integrate payment gateway here
    # For now, simulate successful payment and add slots
    url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    # Convert amount to kobo (Paystack uses kobo, not naira)
    amount_in_kobo = int(pkg.price * 100)
    
    # Construct dynamic callback URL
    callback_url = request.build_absolute_uri(reverse('listings:verify_payment'))
    
    data = {
        "email": request.user.email,
        "amount": amount_in_kobo,
        "currency": "NGN",
        "reference": f"{pkg.id}",
        "callback_url": callback_url,
        "metadata": {
            "listing_id": str(pkg.id),
            "customer_name": request.user.get_full_name(),
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response_data = response.json()
        
        # Debug logging
        print(f"Paystack Response Status Code: {response.status_code}")
        print(f"Paystack Response Data: {response_data}")
        
        if response_data.get('status'):
            # Redirect to Paystack payment page
            authorization_url = response_data['data']['authorization_url']
            print(f"Redirecting to: {authorization_url}")
            return redirect(authorization_url)
        else:
            error_message = response_data.get('message', 'Unknown error')
            print(f"Paystack Error: {error_message}")
            messages.error(request, f'Payment initialization failed: {error_message}')
            return redirect('shop:profile')
            
    except requests.exceptions.RequestException as e:
        print(f"Network Error: {str(e)}")
        messages.error(request, f'Network error: Unable to connect to payment gateway. Please try again.')
        return redirect('shop:profile')
    except Exception as e:
        print(f"Payment Error: {str(e)}")
        messages.error(request, f'Payment initialization error: {str(e)}')
        return redirect('shop:profile')
    """
    # Add purchased slots to user's total (cumulative)
    sub.add_slots(pkg.slots_count)
    sub.package = pkg  # Update reference to last purchased package
    sub.save()
    
    messages.success(
        request, 
        f"Successfully purchased {pkg.name} package! {pkg.slots_count} slots added. "
        f"You now have {sub.total_slots} total slots ({sub.remaining_slots} remaining)."
    )
    return redirect('listings:dashboard')
    """
    
    
def verify_payment(request):
    pass    
