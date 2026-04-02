# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Property, State, City, PropertyType, PropertyApplication
from listings.models import SavedProperty
import logging

logger = logging.getLogger(__name__)


def homepage(request):
    """Homepage with property search"""
    
    try:
        # Get all states for dropdown
        states = State.objects.filter(is_active=True)
        
        # Get property types
        property_types = PropertyType.objects.all()
        
        # Featured properties
        featured_properties = Property.objects.filter(
            is_featured=True
        ).select_related('state', 'city', 'property_type', 'status', 'agent', 'listed_by')[:6]
        
        # Premium properties for carousel
        premium_properties = Property.objects.filter(
            is_premium=True
        ).select_related('state', 'city', 'property_type', 'status', 'agent', 'listed_by').order_by('-created_at')[:3]
        print("This is premium properties", premium_properties)
        # Get all properties for display
        all_properties = Property.objects.select_related(
            'state', 'city', 'property_type', 'status'
        )[:10]
        
        # Get pricing packages for "Sell Your Properties" section
        from listings.models import ListingPackage
        pricing_packages = ListingPackage.objects.filter(is_active=True).order_by('price')[:4]
        
        # Get recent blog posts
        from blogs.models import Post
        recent_blog_posts = Post.objects.filter(
            status='published'
        ).select_related('author', 'category').order_by('-publish')[:3]

        # Get featured agents for homepage
        from agents.models import Agent
        featured_agents = Agent.objects.filter(
            is_active=True,
            verification_status='verified'
        ).select_related('user')[:6]

        context = {
            'states': states,
            'property_types': property_types,
            'featured_properties': featured_properties,
            'premium_properties': premium_properties,
            'all_properties': all_properties,
            'pricing_packages': pricing_packages,
            'recent_blog_posts': recent_blog_posts,
            'latest_posts': recent_blog_posts,  # alias for index.html template
            'featured_agents': featured_agents,
        }

        return render(request, 'estate/index.html', context)

    except Exception as e:
        logger.error(f"Error in homepage view: {str(e)}", exc_info=True)
        # Return a minimal context to prevent complete failure
        return render(request, 'estate/index.html', {
            'states': [],
            'property_types': [],
            'featured_properties': [],
            'all_properties': [],
            'pricing_packages': [],
            'recent_blog_posts': [],
            'latest_posts': [],
            'error_message': 'Some content may not be available at the moment.',
        })


def get_cities_by_state(request):
    """AJAX endpoint to get cities for a selected state"""
    state_id = request.GET.get('state_id')
    
    if not state_id:
        return JsonResponse({'cities': []})
    
    try:
        cities = City.objects.filter(
            state_id=state_id,
            is_active=True
        ).values('id', 'name')
        
        return JsonResponse({
            'cities': list(cities)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def search_properties(request):
    """Search/filter properties"""
    
    # Get filter parameters
    state_id = request.GET.get('state_type')
    city_id = request.GET.get('city_type')
    property_type = request.GET.get('property_type')
    price_range = request.GET.get('price_range')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    
    # Start with all properties
    properties = Property.objects.select_related(
        'state', 'city', 'property_type', 'status'
    )
    
    # Apply filters
    if state_id:
        properties = properties.filter(state_id=state_id)
    
    if city_id:
        properties = properties.filter(city_id=city_id)
    
    if property_type:
        properties = properties.filter(property_type__name=property_type)
    
    if price_range:
        if price_range == '1200000+':
            properties = properties.filter(price__gte=1200000)
        elif '-' in price_range:
            min_price, max_price = price_range.split('-')
            properties = properties.filter(price__gte=int(min_price), price__lte=int(max_price))
    
    if bedrooms:
        if bedrooms == '5+':
            properties = properties.filter(bedrooms__gte=5)
        else:
            properties = properties.filter(bedrooms=int(bedrooms))
    
    if bathrooms:
        if bathrooms == '4+':
            properties = properties.filter(bathrooms__gte=4)
        else:
            properties = properties.filter(bathrooms=int(bathrooms))
    
    context = {
        'properties': properties,
        'search_params': request.GET,
    }
    
    return render(request, 'estate/search_results.html', context)


def get_properties_details(request, slug):
    property_detail = get_object_or_404(Property, slug=slug)

    # ── Saved property check ─────────────────────────────────────────────────
    saved_property = None
    if request.user.is_authenticated:
        try:
            saved_property = SavedProperty.objects.get(user=request.user, property=property_detail)
        except SavedProperty.DoesNotExist:
            saved_property = None

    # ── Application form setup ───────────────────────────────────────────────
    from .forms import PropertyApplicationForm

    # Check if user already submitted an application for this property
    existing_application = None
    if request.user.is_authenticated:
        existing_application = PropertyApplication.objects.filter(
            listing=property_detail,
            applicant=request.user
        ).first()

    application_form = None
    application_success = False

    # ── POST: could be a save-property action OR an application submission ───
    if request.method == "POST":
        # ── POST: Save property (original behaviour, triggered by save button)
        if 'save_property' in request.POST:
            try:
                SavedProperty.objects.create(user=request.user, property=property_detail)
                return JsonResponse({
                    "status": "success",
                    "message": f"{property_detail.title} saved successfully"
                })
            except Exception as e:
                return JsonResponse({
                    "status": "error",
                    "message": f"Error saving property: {str(e)}"
                })

        # ── POST: Application form submission ────────────────────────────────
        elif 'submit_application' in request.POST:
            application_form = PropertyApplicationForm(request.POST, request.FILES)
            if application_form.is_valid():
                application = application_form.save(commit=False)
                application.listing = property_detail
                if request.user.is_authenticated:
                    application.applicant = request.user
                application.save()
                application_success = True
                application_form = None  # Clear form after success
            # If invalid, the form with errors falls through to the context below

    # ── GET (or failed POST): build a blank / pre-filled form ────────────────
    if application_form is None and not application_success:
        initial = {}
        # Pre-fill realtor fields if the logged-in user is an agent
        if request.user.is_authenticated and hasattr(request.user, 'agent_profile'):
            agent = request.user.agent_profile
            initial = {
                'realtor_name':  agent.user.get_full_name(),
                'realtor_email': agent.user.email,
                'realtor_phone': getattr(agent, 'phone_number', ''),
                'realtor_cid':   getattr(agent, 'agent_code', ''),
            }
        # Pre-fill personal details if user is already logged in
        if request.user.is_authenticated:
            initial.update({
                'email':     request.user.email,
                'firstname': request.user.first_name,
                'surname':   request.user.last_name,
            })
        application_form = PropertyApplicationForm(initial=initial)

    # ── Referral tracking ────────────────────────────────────────────────────
    ref_code = request.GET.get('ref')
    if ref_code:
        from agents.utils import store_property_referral
        store_property_referral(request, property_detail.id, ref_code)

    # ── Generate referral link for logged-in agents ──────────────────────────
    referral_link = None
    if request.user.is_authenticated and hasattr(request.user, 'agent_profile'):
        from agents.utils import generate_property_referral_url
        referral_link = generate_property_referral_url(request, property_detail, request.user.agent_profile)

    context = {
        'property':              property_detail,
        'referral_link':         referral_link,
        'saved_property':        saved_property is not None,

        # Application form context
        'application_form':      application_form,
        'existing_application':  existing_application,
        'application_success':   application_success,

        # Price reference table for the JS live calculator in the template
        'price_table': {
            'ground_3month':   40_000_000,
            'ground_6month':   40_500_000,
            'upper_3month':    37_000_000,
            'upper_6month':    37_500_000,
            'initial_deposit': 10_000_000,
            'dev_doc_fee':      2_500_000,
        },
    }
    return render(request, 'estate/property-details.html', context)


def property_list(request):
    """List all properties with pagination, filtering, and sorting"""
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Base Queryset
    properties_list = Property.objects.select_related(
        'state', 'city', 'property_type', 'status', 'listed_by'
    ).filter(status__name__in=['for_sale', 'for_rent', 'pending']) # Show active listings
    
    # --- Filtering ---
    
    # Keyword Search (e.g. from global search)
    query = request.GET.get('q')
    if query:
        properties_list = properties_list.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(city__name__icontains=query)
        )

    state_id = request.GET.get('state_type')
    if state_id:
        properties_list = properties_list.filter(state_id=state_id)

    listing_type = request.GET.get('listing_type')
    if listing_type and listing_type not in ('', 'buy'):
        properties_list = properties_list.filter(status__name__icontains=listing_type)    

    # City filter (from homepage search form)
    city_id = request.GET.get('city_type')
    if city_id:
        properties_list = properties_list.filter(city_id=city_id)   

    # Property Type
    prop_type = request.GET.get('type')
    if prop_type and prop_type != 'All Types':
        properties_list = properties_list.filter(property_type__name=prop_type)

    # Price Range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        properties_list = properties_list.filter(price__gte=min_price)
    if max_price:
        properties_list = properties_list.filter(price__lte=max_price)

    # Bedrooms
    bedrooms = request.GET.get('bedrooms')
    if bedrooms and bedrooms != 'Any':
        if '+' in bedrooms:
            val = int(bedrooms.replace('+', ''))
            properties_list = properties_list.filter(bedrooms__gte=val)
        else:
            properties_list = properties_list.filter(bedrooms=int(bedrooms))

    # Bathrooms
    bathrooms = request.GET.get('bathrooms')
    if bathrooms and bathrooms != 'Any':
        if '+' in bathrooms:
            val = int(bathrooms.replace('+', ''))
            properties_list = properties_list.filter(bathrooms__gte=val)
        else:
            properties_list = properties_list.filter(bathrooms=int(bathrooms))
            
    # Location (Text search for City/State/Address)
    location = request.GET.get('location')
    if location:
        properties_list = properties_list.filter(
            Q(city__name__icontains=location) | 
            Q(state__name__icontains=location) |
            Q(address__icontains=location)
        )
        
    # Features
    if request.GET.get('garage'):
        properties_list = properties_list.filter(has_garage=True)
    if request.GET.get('pool'):
        properties_list = properties_list.filter(has_pool=True)
    if request.GET.get('balcony'):
        properties_list = properties_list.filter(has_balcony=True)
    if request.GET.get('garden'):
        properties_list = properties_list.filter(has_garden=True)
    if request.GET.get('security'):
        properties_list = properties_list.filter(has_security=True)
    if request.GET.get('gym'):
        properties_list = properties_list.filter(has_gym=True)
    if request.GET.get('furnished'):
        properties_list = properties_list.filter(is_furnished=True)
    if request.GET.get('ac'):
        properties_list = properties_list.filter(has_ac=True)
    if request.GET.get('has_heating'):
        properties_list = properties_list.filter(has_heating=True)
    if request.GET.get('pets'):
        properties_list = properties_list.filter(pet_friendly=True)             

    # --- Sorting ---
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_asc':
        properties_list = properties_list.order_by('price')
    elif sort_by == 'price_desc':
        properties_list = properties_list.order_by('-price')
    elif sort_by == 'views':
        properties_list = properties_list.order_by('-views_count')
    else: # newest
        properties_list = properties_list.order_by('-created_at')

    
    # --- Pagination ---
    paginator = Paginator(properties_list, 9) 
    page_number = request.GET.get('page')
    properties = paginator.get_page(page_number)
    
    # Get Filter Options for Sidebar
    property_types = PropertyType.objects.all()
    
    # Sidebar Featured Properties (limit 3)
    featured_sidebar = Property.objects.filter(is_featured=True).exclude(status__name='sold').order_by('-created_at')[:3]
    
    context = {
        'properties': properties,
        'property_types': property_types,
        'search_params': request.GET, # To keep filter values in inputs
        'featured_sidebar': featured_sidebar,
    }
    
    return render(request, 'estate/properties.html', context)