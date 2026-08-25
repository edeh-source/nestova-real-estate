# views.py
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from .models import Property, State, City, PropertyType, PropertyApplication, Developer, PaymentAccount
from listings.models import SavedProperty
from django.conf import settings
import logging
from urllib.parse import quote


logger = logging.getLogger(__name__)


@cache_page(60 * 15)
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

        # Get featured developers for homepage
        featured_developers = Developer.objects.filter(
            is_featured=True,
            is_active=True
        ).order_by('-created_at')[:5]

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
            'featured_developers': featured_developers,
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
            'featured_developers': [],
            'error_message': 'Some content may not be available at the moment.',
        })


def get_cities_by_state(request):
    """AJAX endpoint to get cities for a selected state. Auto-seeds from Nigeria dataset if empty."""
    state_id = request.GET.get('state_id')

    if not state_id:
        return JsonResponse({'cities': []})

    try:
        state_obj = State.objects.get(id=state_id)

        cities = City.objects.filter(state=state_obj, is_active=True).order_by('name')

        # Auto-seed cities from built-in Nigeria dataset if the state has no cities yet
        if not cities.exists():
            try:
                from property.nigeria_locations import NIGERIA_LOCATIONS, seed_nigeria_locations
                loc_data = NIGERIA_LOCATIONS.get(state_obj.name)
                if loc_data:
                    for c_name in loc_data['cities']:
                        City.objects.get_or_create(
                            name=c_name,
                            state=state_obj,
                            defaults={'is_active': True}
                        )
                    cities = City.objects.filter(state=state_obj, is_active=True).order_by('name')
            except Exception:
                pass

        return JsonResponse({
            'status': 'success',
            'state_id': state_obj.id,
            'state_name': state_obj.name,
            'cities': list(cities.values('id', 'name'))
        })

    except State.DoesNotExist:
        return JsonResponse({'status': 'error', 'cities': [], 'message': 'State not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e), 'cities': []}, status=400)


def search_properties(request):
    """Search/filter properties"""
    from django.db.models import Q
    
    # Get filter parameters
    state_id = request.GET.get('state_type') or request.GET.get('state')
    city_id = request.GET.get('city_type') or request.GET.get('city')
    listing_type = request.GET.get('listing_type')
    category = request.GET.get('category')
    property_type = request.GET.get('type') or request.GET.get('property_type')
    price_range = request.GET.get('price_range')
    bedrooms = request.GET.get('bedrooms')
    bathrooms = request.GET.get('bathrooms')
    
    # Start with all properties
    properties = Property.objects.select_related(
        'state', 'city', 'property_type', 'status'
    )
    
    # Apply filters
    if state_id:
        if str(state_id).isdigit():
            properties = properties.filter(state_id=state_id)
        else:
            properties = properties.filter(state__name__icontains=state_id)
    
    if city_id:
        if str(city_id).isdigit():
            properties = properties.filter(city_id=city_id)
        else:
            properties = properties.filter(city__name__icontains=city_id)

    if category and category.lower() != 'all':
        properties = properties.filter(
            Q(property_type__category__iexact=category) |
            Q(property_type__name__icontains=category)
        )

    if listing_type:
        lt_lower = listing_type.lower()
        if lt_lower == 'commercial':
            properties = properties.filter(
                Q(property_type__category__iexact='commercial') |
                Q(property_type__name__icontains='commercial')
            )
        elif lt_lower == 'land':
            properties = properties.filter(
                Q(property_type__category__iexact='land') |
                Q(property_type__name__icontains='land')
            )
        elif lt_lower in ('buy', 'sale', 'for_sale'):
            properties = properties.filter(status__name__icontains='sale')
        elif lt_lower in ('rent', 'for_rent'):
            properties = properties.filter(status__name__icontains='rent')
        else:
            properties = properties.filter(
                Q(status__name__icontains=listing_type) |
                Q(property_type__category__iexact=listing_type) |
                Q(property_type__name__icontains=listing_type)
            )
    
    if property_type and property_type != 'All Types':
        properties = properties.filter(
            Q(property_type__name__iexact=property_type) |
            Q(property_type__category__iexact=property_type) |
            Q(property_type__name__icontains=property_type)
        )
    
    if price_range:
        if '+' in price_range:
            p_val = price_range.replace('+', '').strip()
            if p_val.isdigit():
                properties = properties.filter(price__gte=int(p_val))
        elif '-' in price_range:
            parts = price_range.split('-')
            if len(parts) == 2:
                p_min, p_max = parts[0].strip(), parts[1].strip()
                if p_min.isdigit():
                    properties = properties.filter(price__gte=int(p_min))
                if p_max.isdigit():
                    properties = properties.filter(price__lte=int(p_max))
    
    if bedrooms:
        if bedrooms == '5+':
            properties = properties.filter(bedrooms__gte=5)
        elif str(bedrooms).isdigit():
            properties = properties.filter(bedrooms=int(bedrooms))
    
    if bathrooms:
        if bathrooms == '4+':
            properties = properties.filter(bathrooms__gte=4)
        elif str(bathrooms).isdigit():
            properties = properties.filter(bathrooms=int(bathrooms))
    
    context = {
        'properties': properties,
        'search_params': request.GET,
    }
    
    return render(request, 'estate/search_results.html', context)


def get_properties_details(request, slug):
    property_queryset = Property.objects.select_related(
        'state', 'city', 'property_type', 'status', 'listed_by', 'agent__user'
    ).prefetch_related('images')
    property_detail = get_object_or_404(property_queryset, slug=slug)

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

                # ── Send email notification to admin ─────────────────────────
                try:
                    from django.core.mail import send_mail
                    from django.template.loader import render_to_string
                    from django.utils.html import strip_tags
                    from django.contrib.sites.shortcuts import get_current_site
                    import datetime

                    current_site = get_current_site(request)
                    admin_url = f"https://{current_site.domain}/admin/property/propertyapplication/{application.pk}/change/"

                    email_context = {
                        'property_title': property_detail.title,
                        'applicant_name': application.get_full_name(),
                        'applicant_email': application.email,
                        'applicant_phone': application.phone_number,
                        'applicant_occupation': application.occupation,
                        'floor_choice': application.get_floor_choice_display() if application.floor_choice else '',
                        'payment_plan': application.get_payment_plan_display() if application.payment_plan else '',
                        'number_of_shops': application.number_of_shops,
                        'realtor_name': application.realtor_name,
                        'realtor_email': application.realtor_email,
                        'realtor_phone': application.realtor_phone,
                        'admin_url': admin_url,
                        'year': datetime.datetime.now().year,
                    }

                    html_message = render_to_string('emails/application_admin_notification.html', email_context)
                    plain_message = strip_tags(html_message)

                    admin_emails = [a[1] for a in settings.ADMINS] if getattr(settings, 'ADMINS', None) else [settings.DEFAULT_FROM_EMAIL]

                    send_mail(
                        subject=f'New Property Application: {property_detail.title} — {application.get_full_name()}',
                        message=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=admin_emails,
                        html_message=html_message,
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Failed to send application notification email: {e}", exc_info=True)

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

    # ── Payment accounts for application form ────────────────────────────────
    payment_accounts = PaymentAccount.objects.filter(is_active=True)

    context = {
        'property':              property_detail,
        'referral_link':         referral_link,
        'saved_property':        saved_property is not None,

        # Application form context
        'application_form':      application_form,
        'existing_application':  existing_application,
        'application_success':   application_success,
        'payment_accounts':      payment_accounts,
        

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
    whatsapp_msg = quote(f"Hi, I'm interested in {property_detail.title}. Please send me more details.")
    context['whatsapp_url']    = f"https://wa.me/{settings.WHATSAPP_NUMBER}?text={whatsapp_msg}"
    context['contact_phone']   = settings.CONTACT_PHONE
    return render(request, 'estate/property-details.html', context)


def property_list(request):
    """List all properties with pagination, filtering, and sorting"""
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    # Base Queryset
    properties_list = Property.objects.select_related(
        'state', 'city', 'property_type', 'status', 'listed_by', 'agent__user'
    ).prefetch_related('images').filter(status__name__in=['for_sale', 'for_rent', 'pending']) # Show active listings
    
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

    # State filter (handles state_type ID from homepage and state name/ID from sidebar)
    state_param = request.GET.get('state_type') or request.GET.get('state')
    if state_param:
        if str(state_param).isdigit():
            properties_list = properties_list.filter(state_id=state_param)
        else:
            properties_list = properties_list.filter(state__name__icontains=state_param)

    # City filter (handles city_type ID from homepage and city name/ID from sidebar)
    city_param = request.GET.get('city_type') or request.GET.get('city')
    if city_param:
        if str(city_param).isdigit():
            properties_list = properties_list.filter(city_id=city_param)
        else:
            properties_list = properties_list.filter(city__name__icontains=city_param)

    # Category Filter (Residential / Commercial / Land / Special)
    category = request.GET.get('category')
    if category and category.lower() != 'all':
        properties_list = properties_list.filter(
            Q(property_type__category__iexact=category) |
            Q(property_type__name__icontains=category)
        )

    # Listing Type / Homepage Tabs (buy, commercial, land, rent)
    listing_type = request.GET.get('listing_type')
    if listing_type:
        listing_type_lower = listing_type.lower()
        if listing_type_lower == 'commercial':
            properties_list = properties_list.filter(
                Q(property_type__category__iexact='commercial') |
                Q(property_type__name__icontains='commercial')
            )
        elif listing_type_lower == 'land':
            properties_list = properties_list.filter(
                Q(property_type__category__iexact='land') |
                Q(property_type__name__icontains='land')
            )
        elif listing_type_lower in ('buy', 'sale', 'for_sale'):
            properties_list = properties_list.filter(status__name__icontains='sale')
        elif listing_type_lower in ('rent', 'for_rent'):
            properties_list = properties_list.filter(status__name__icontains='rent')
        else:
            properties_list = properties_list.filter(
                Q(status__name__icontains=listing_type) |
                Q(property_type__category__iexact=listing_type) |
                Q(property_type__name__icontains=listing_type)
            )

    # Specific Property Type
    prop_type = request.GET.get('type') or request.GET.get('property_type')
    if prop_type and prop_type != 'All Types':
        type_filter = (
            Q(property_type__name__iexact=prop_type) |
            Q(property_type__category__iexact=prop_type) |
            Q(property_type__name__icontains=prop_type)
        )
        properties_list = properties_list.filter(type_filter)

    # Price Range (supports dropdown formats like "0-5000000", "500000000-999999999", "1200000+" and individual min/max inputs)
    price_range = request.GET.get('price_range')
    if price_range:
        if '+' in price_range:
            p_val = price_range.replace('+', '').strip()
            if p_val.isdigit():
                properties_list = properties_list.filter(price__gte=int(p_val))
        elif '-' in price_range:
            parts = price_range.split('-')
            if len(parts) == 2:
                p_min, p_max = parts[0].strip(), parts[1].strip()
                if p_min.isdigit():
                    properties_list = properties_list.filter(price__gte=int(p_min))
                if p_max.isdigit():
                    properties_list = properties_list.filter(price__lte=int(p_max))

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price and str(min_price).strip().isdigit():
        properties_list = properties_list.filter(price__gte=int(min_price.strip()))
    if max_price and str(max_price).strip().isdigit():
        properties_list = properties_list.filter(price__lte=int(max_price.strip()))

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
    paginator = Paginator(properties_list, 12) 
    page_number = request.GET.get('page')
    properties = paginator.get_page(page_number)
    
    # Get Filter Options for Sidebar
    property_types = PropertyType.objects.all()
    
    # Sidebar Featured Properties (limit 3)
    featured_sidebar = Property.objects.filter(is_featured=True).exclude(status__name='sold').select_related('city', 'state', 'status').prefetch_related('images').order_by('-created_at')[:3]
    
    context = {
        'properties': properties,
        'property_types': property_types,
        'search_params': request.GET, # To keep filter values in inputs
        'featured_sidebar': featured_sidebar,
    }
    
    return render(request, 'estate/properties.html', context)

# ==================== DEVELOPER VIEWS ====================

def developers_list(request):
    """Public listing of all active developers"""
    from django.core.paginator import Paginator

    developers = Developer.objects.filter(is_active=True).order_by('-is_featured', 'name')
    paginator = Paginator(developers, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'estate/developers.html', {
        'page_obj': page_obj,
        'developers': page_obj,
        'total_count': developers.count(),
    })


def developer_detail(request, slug):
    """Developer profile page with tabbed properties"""
    from django.core.paginator import Paginator

    developer = get_object_or_404(Developer, slug=slug, is_active=True)
    all_props = developer.properties.filter(is_active=True).select_related(
        'state', 'city', 'property_type', 'status'
    )

    # Tab filtering
    listing_type = request.GET.get('type', 'all')
    if listing_type == 'sale':
        props = all_props.filter(status__name='for_sale')
    elif listing_type == 'rent':
        props = all_props.filter(status__name='for_rent')
    else:
        props = all_props

    paginator = Paginator(props, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Property counts for tabs
    tab_counts = {
        'all': all_props.count(),
        'sale': all_props.filter(status__name='for_sale').count(),
        'rent': all_props.filter(status__name='for_rent').count(),
    }

    return render(request, 'estate/developer_detail.html', {
        'developer': developer,
        'page_obj': page_obj,
        'properties': page_obj,
        'listing_type': listing_type,
        'tab_counts': tab_counts,
    })
