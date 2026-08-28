import uuid
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Case, When, Value, IntegerField, F

from .models import ListingPackage, UserSubscription, PaymentRecord
from .forms import PropertyForm
from property.models import Property, PropertyImage


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _boosted_property_qs(qs):
    """
    Apply PropertyPro-style ordering to any Property queryset:
        1. Tier rank: sponsored > premium_gold > premium > standard
        2. Within each tier: most recently boosted first
        3. Fallback: newest listing first
    """
    tier_rank = Case(
        When(boost_tier='sponsored',    then=Value(0)),
        When(boost_tier='premium_gold', then=Value(1)),
        When(boost_tier='premium',      then=Value(2)),
        default=Value(3),
        output_field=IntegerField()
    )
    return qs.annotate(tier_rank=tier_rank).order_by(
        'tier_rank',
        F('boosted_at').desc(nulls_last=True),
        '-created_at'
    )


def _get_or_create_sub(user) -> UserSubscription:
    sub, created = UserSubscription.objects.get_or_create(user=user)
    if created or not sub.package:
        default_pkg = ListingPackage.objects.filter(is_default=True, is_active=True).first()
        if default_pkg and not sub.package:
            sub.package = default_pkg
            sub.save(update_fields=['package'])
    return sub


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """
    User dashboard — shows active listings, slot/boost usage, and fires a
    pending auto-boost inline if one is due (fallback for installs without
    Celery / cron).
    """
    sub = _get_or_create_sub(request.user)

    # Inline auto-boost fallback
    if sub.needs_auto_boost():
        boosted_count = sub.perform_auto_boost()
        if boosted_count > 0:
            messages.info(
                request,
                f"✨ Auto-boost fired: {boosted_count} "
                f"{'listing' if boosted_count == 1 else 'listings'} pushed to the top."
            )

    # Warn on expired subscription
    if sub.package and sub.is_expired:
        messages.warning(
            request,
            "⚠️ Your subscription has expired. Renew to keep your listings boosted."
        )

    user_properties = _boosted_property_qs(
        Property.objects.filter(listed_by=request.user)
    )

    context = {
        'subscription':   sub,
        'properties':     user_properties,
        # Backward-compat keys for existing templates
        'used_slots':     sub.get_used_slots(),
        'remaining_slots': sub.remaining_slots,
        'has_package':    sub.package is not None,
        # Boost-aware context
        'manual_boosts_remaining':      sub.manual_boosts_remaining,
        'premium_slots_remaining':      sub.premium_slots_remaining,
        'premium_gold_slots_remaining': sub.premium_gold_slots_remaining,
        'sponsored_slots_remaining':    sub.sponsored_slots_remaining,
        'next_auto_boost_at':           sub.next_auto_boost_at,
        'last_auto_boost_at':           sub.last_auto_boost_at,
        'subscription_expires':         sub.end_date,
        'remaining_days':               sub.remaining_days,
    }
    return render(request, 'listings/dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Post / Edit property
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def post_property(request):
    """Post a new property. Enforces listing-limit and ID-verification gates."""
    sub = _get_or_create_sub(request.user)

    if not sub.has_remaining_listings():
        messages.warning(
            request,
            f"You have used all {sub.listing_limit} listing slots on your current plan. "
            "Upgrade to post more properties."
        )
        return redirect('listings:pricing')

    # ── Verification gate ─────────────────────────────────────────────────────
    can_post = False
    if hasattr(request.user, 'agent_profile'):
        agent = request.user.agent_profile
        if agent.can_post_properties or getattr(request.user, 'can_post_properties', False):
            can_post = True
        elif isinstance(agent.verification_data, dict):
            score = agent.verification_data.get('confidence_score')
            if score is not None and float(score) >= 70:
                agent.can_post_properties = True
                agent.id_verified = True
                agent.save(update_fields=['can_post_properties', 'id_verified'])
                request.user.can_post_properties = True
                request.user.id_verified = True
                request.user.save(update_fields=['can_post_properties', 'id_verified'])
                can_post = True

        if not can_post:
            messages.warning(request, "Your account must be verified before posting properties.")
            return redirect('agents:verification_dashboard')

    elif hasattr(request.user, 'company_profile'):
        company = request.user.company_profile
        if company.can_post_properties or getattr(request.user, 'can_post_properties', False):
            can_post = True
        elif isinstance(company.cac_data, dict):
            score = company.cac_data.get('name_match_score')
            if score is not None and float(score) >= 70:
                company.can_post_properties = True
                company.cac_verified = True
                company.save(update_fields=['can_post_properties', 'cac_verified'])
                request.user.can_post_properties = True
                request.user.save(update_fields=['can_post_properties'])
                can_post = True

        if not can_post:
            messages.warning(request, "Your company account must be verified before posting properties.")
            return redirect('agents:verification_dashboard')

    else:
        if getattr(request.user, 'can_post_properties', False) or getattr(request.user, 'id_verified', False):
            can_post = True
        elif isinstance(getattr(request.user, 'verification_data', {}), dict):
            score = getattr(request.user, 'verification_data', {}).get('confidence_score')
            if score is not None and float(score) >= 70:
                request.user.can_post_properties = True
                request.user.id_verified = True
                request.user.save(update_fields=['can_post_properties', 'id_verified'])
                can_post = True

        if not can_post:
            messages.warning(request, "You must verify your identity before posting properties.")
            return redirect('users:submit_user_verification')

    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            # Re-check limit (guard against race condition)
            if not sub.has_remaining_listings():
                messages.error(request, "No listing slots available. Please upgrade your plan.")
                return redirect('listings:pricing')

            property_obj            = form.save(commit=False)
            property_obj.listed_by  = request.user
            # New listings get an immediate boost timestamp so they appear near the top
            property_obj.boosted_at = timezone.now()
            property_obj.save()

            for idx, image in enumerate(request.FILES.getlist('secondary_images')):
                PropertyImage.objects.create(
                    property=property_obj,
                    image=image,
                    is_primary=False,
                    order=idx
                )

            messages.success(
                request,
                f"Property posted! You have {sub.remaining_listings} "
                f"listing {'slot' if sub.remaining_listings == 1 else 'slots'} remaining."
            )
            return redirect('shop:profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PropertyForm()

    return render(request, 'listings/post_property.html', {
        'form':            form,
        'remaining_slots': sub.remaining_listings,
        'total_slots':     sub.listing_limit,
        'used_slots':      sub.active_listing_count,
        'is_edit':         False,
    })


@login_required
def edit_property(request, slug):
    """Edit an existing property (owner-only)."""
    property_obj = get_object_or_404(Property, slug=slug)

    if property_obj.listed_by != request.user:
        messages.error(request, "You don't have permission to edit this property.")
        return redirect('shop:profile')

    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property_obj)
        if form.is_valid():
            property_obj = form.save()

            for idx, image in enumerate(request.FILES.getlist('secondary_images')):
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

    return render(request, 'listings/post_property.html', {
        'form':            form,
        'property':        property_obj,
        'existing_images': PropertyImage.objects.filter(
                               property=property_obj, is_primary=False
                           ).order_by('order'),
        'is_edit':         True,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Pricing
# ─────────────────────────────────────────────────────────────────────────────

def pricing_plans(request):
    """Show available subscription plans."""
    packages = ListingPackage.objects.filter(is_active=True).order_by('price')

    user_subscription = None
    if request.user.is_authenticated:
        user_subscription = _get_or_create_sub(request.user)

    return render(request, 'listings/pricing.html', {
        'packages':          packages,
        'user_subscription': user_subscription,
    })


def package_detail(request, slug):
    """Detailed breakdown and explanation page for a specific listing slot package."""
    package = get_object_or_404(ListingPackage, slug=slug, is_active=True)
    other_packages = ListingPackage.objects.filter(is_active=True).exclude(id=package.id).order_by('price')

    user_subscription = None
    is_current_plan = False
    if request.user.is_authenticated:
        user_subscription = _get_or_create_sub(request.user)
        if user_subscription and user_subscription.package == package:
            is_current_plan = True

    return render(request, 'listings/package_detail.html', {
        'package':           package,
        'other_packages':    other_packages,
        'user_subscription': user_subscription,
        'is_current_plan':   is_current_plan,
    })


# ─────────────────────────────────────────────────────────────────────────────
# Payment — subscribe & verify
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def subscribe(request, package_id):
    """
    Initialise a Paystack transaction for the selected package.
    Redirects the user to Paystack's hosted payment page.
    """
    pkg = get_object_or_404(ListingPackage, id=package_id, is_active=True)

    # Unique, traceable reference
    reference = f"nestova_{request.user.id}_{pkg.id}_{uuid.uuid4().hex[:10]}"

    # Create a pending payment record for idempotent verification
    payment, _ = PaymentRecord.objects.get_or_create(
        reference=reference,
        defaults={
            'user':    request.user,
            'package': pkg,
            'amount':  pkg.price,
            'status':  'pending',
        }
    )

    callback_url = request.build_absolute_uri(reverse('listings:verify_payment'))

    payload = {
        "email":        request.user.email,
        "amount":       int(pkg.price * 100),   # Paystack uses kobo
        "currency":     "NGN",
        "reference":    reference,
        "callback_url": callback_url,
        "metadata": {
            "package_id":    str(pkg.id),
            "user_id":       str(request.user.id),
            "package_name":  pkg.name,
            "customer_name": request.user.get_full_name() or request.user.username,
        }
    }

    try:
        resp = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json()

        if data.get('status'):
            return redirect(data['data']['authorization_url'])

        payment.status            = 'failed'
        payment.paystack_response = data
        payment.save(update_fields=['status', 'paystack_response'])
        messages.error(request, f"Payment init failed: {data.get('message', 'Unknown error')}")
        return redirect('listings:pricing')

    except requests.exceptions.Timeout:
        messages.error(request, "Payment gateway timed out. Please try again.")
        return redirect('listings:pricing')
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Network error: {e}")
        return redirect('listings:pricing')


def verify_payment(request):
    """
    Paystack redirects here after payment with ?reference=xxx.

    Flow:
    1. Pull reference from query params.
    2. Check PaymentRecord — if already 'success', skip (idempotent).
    3. Call Paystack verify endpoint.
    4. On success → activate the package on the user's subscription.
    """
    reference = request.GET.get('reference') or request.GET.get('trxref')

    if not reference:
        messages.error(request, "No payment reference found in the callback.")
        return redirect('listings:pricing')

    # ── Idempotency check ─────────────────────────────────────────────────────
    try:
        payment = PaymentRecord.objects.get(reference=reference)
    except PaymentRecord.DoesNotExist:
        messages.error(request, "Unknown payment reference. Please contact support.")
        return redirect('listings:pricing')

    if payment.status == 'success':
        messages.info(request, "This payment has already been processed. ✅")
        return redirect('listings:dashboard')

    # ── Verify with Paystack ──────────────────────────────────────────────────
    try:
        resp = requests.get(
            f"https://api.paystack.co/transaction/verify/{reference}",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            timeout=15,
        )
        data = resp.json()
    except requests.exceptions.RequestException as e:
        messages.error(request, f"Could not reach payment gateway: {e}")
        return redirect('listings:pricing')

    payment.paystack_response = data
    ps_data = data.get('data', {})

    if not data.get('status') or ps_data.get('status') != 'success':
        payment.status = 'failed'
        payment.save(update_fields=['status', 'paystack_response'])
        messages.error(
            request,
            "Payment was not successful. If money was deducted, please contact support."
        )
        return redirect('listings:pricing')

    # ── Activate the package ──────────────────────────────────────────────────
    package_id = ps_data.get('metadata', {}).get('package_id') or str(payment.package_id)

    try:
        pkg = ListingPackage.objects.get(id=package_id, is_active=True)
    except ListingPackage.DoesNotExist:
        messages.error(request, "Package no longer available. Please contact support.")
        return redirect('listings:pricing')

    target_user = payment.user if request.user.is_authenticated else None
    if target_user is None:
        messages.error(request, "Session expired. Please log in and try again.")
        return redirect('users:login')

    sub = _get_or_create_sub(target_user)
    sub.activate_package(pkg)

    payment.status  = 'success'
    payment.package = pkg
    payment.save(update_fields=['status', 'package', 'paystack_response'])

    messages.success(
        request,
        f"🎉 Payment confirmed! Your {pkg.name} plan is now active. "
        f"You can list up to {pkg.listing_limit} properties and your listings "
        f"will auto-boost every {pkg.auto_boost_interval_days} days."
    )
    return redirect('shop:profile')


# ─────────────────────────────────────────────────────────────────────────────
# Manual boost
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def manual_boost(request, property_slug):
    """
    Spend one manual-boost credit to push a specific listing to the top of
    search results immediately.
    """
    property_obj = get_object_or_404(Property, slug=property_slug, listed_by=request.user)
    sub          = _get_or_create_sub(request.user)

    if sub.manual_boosts_remaining <= 0:
        messages.error(
            request,
            "You have no manual boost credits remaining this cycle. "
            + ("Upgrade your plan to get more." if not sub.package else "")
        )
        return redirect('listings:dashboard')

    success = sub.use_manual_boost(property_obj)
    if success:
        messages.success(
            request,
            f"✅ '{property_obj.title}' pushed to the top! "
            f"({sub.manual_boosts_remaining} manual boosts remaining this cycle)"
        )
    else:
        messages.error(request, "Manual boost failed. Please try again.")

    return redirect('listings:dashboard')


# ─────────────────────────────────────────────────────────────────────────────
# Premium tier upgrade
# ─────────────────────────────────────────────────────────────────────────────

TIER_DISPLAY = {
    'premium':      'Premium (5× exposure)',
    'premium_gold': 'Premium Gold (10× exposure)',
    'sponsored':    'Sponsored (20× exposure)',
}

TIER_CREDIT_FIELD = {
    'premium':      'premium_slots_remaining',
    'premium_gold': 'premium_gold_slots_remaining',
    'sponsored':    'sponsored_slots_remaining',
}


@login_required
def apply_premium_tier(request, property_slug, tier):
    """
    Upgrade a specific property to a higher-visibility tier:
        /listings/boost/tier/<slug>/premium/
        /listings/boost/tier/<slug>/premium_gold/
        /listings/boost/tier/<slug>/sponsored/
    """
    if tier not in TIER_DISPLAY:
        messages.error(request, "Invalid boost tier.")
        return redirect('listings:dashboard')

    property_obj = get_object_or_404(Property, slug=property_slug, listed_by=request.user)
    sub          = _get_or_create_sub(request.user)

    remaining = getattr(sub, TIER_CREDIT_FIELD[tier])
    if remaining <= 0:
        messages.error(
            request,
            f"No {TIER_DISPLAY[tier]} credits remaining. Upgrade your plan to unlock more."
        )
        return redirect('listings:dashboard')

    success = sub.apply_premium_tier(property_obj, tier)
    if success:
        messages.success(
            request,
            f"🚀 '{property_obj.title}' is now a {TIER_DISPLAY[tier]} listing! "
            f"({remaining - 1} credits remaining)"
        )
    else:
        messages.error(request, "Tier upgrade failed. Please try again.")

    return redirect('listings:dashboard')


# ─────────────────────────────────────────────────────────────────────────────
# Location APIs (Nigerian States & Cities)
# ─────────────────────────────────────────────────────────────────────────────

def get_states_api(request):
    """Return all active Nigerian states in JSON format. Auto-seeds if empty."""
    from property.models import State
    from property.nigeria_locations import seed_nigeria_locations
    
    if State.objects.count() < 36:
        seed_nigeria_locations()
        
    states = State.objects.filter(is_active=True).order_by('name').values('id', 'name', 'code')
    return JsonResponse({'status': 'success', 'states': list(states)})


def get_cities_by_state(request):
    """
    Return all cities/districts for a given Nigerian state.
    Accepts GET parameter: ?state_id=... or ?state_name=...
    Auto-seeds cities in the database from NIGERIA_LOCATIONS if not yet populated.
    """
    from property.models import State, City
    from property.nigeria_locations import NIGERIA_LOCATIONS, seed_nigeria_locations

    state_id = request.GET.get('state_id')
    state_name = request.GET.get('state_name', '').strip()

    state_obj = None
    if state_id:
        try:
            state_obj = State.objects.get(id=state_id)
        except (State.DoesNotExist, ValueError):
            state_obj = None

    if not state_obj and state_name:
        state_obj = State.objects.filter(name__iexact=state_name).first()

    if not state_obj:
        return JsonResponse({'status': 'error', 'message': 'State not found', 'cities': []}, status=404)

    # Fetch cities from DB
    cities = City.objects.filter(state=state_obj, is_active=True).order_by('name')
    
    # If no cities found in DB, seed from comprehensive dataset
    if not cities.exists():
        loc_data = NIGERIA_LOCATIONS.get(state_obj.name)
        if loc_data:
            for c_name in loc_data['cities']:
                City.objects.get_or_create(name=c_name, state=state_obj, defaults={'is_active': True})
            cities = City.objects.filter(state=state_obj, is_active=True).order_by('name')

    cities_data = list(cities.values('id', 'name'))
    return JsonResponse({
        'status': 'success',
        'state_id': state_obj.id,
        'state_name': state_obj.name,
        'cities': cities_data
    })