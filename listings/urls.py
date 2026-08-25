from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [
    # ── Core ──────────────────────────────────────────────────────────────────
    path('dashboard/',                views.dashboard,      name='dashboard'),
    path('post/',                     views.post_property,  name='post_property'),
    path('edit/<slug:slug>/',         views.edit_property,  name='edit_property'),

    # ── Pricing & payment ─────────────────────────────────────────────────────
    path('pricing/',                  views.pricing_plans,  name='pricing'),
    path('package/<slug:slug>/',      views.package_detail, name='package_detail'),
    path('subscribe/<int:package_id>/', views.subscribe,    name='subscribe'),
    path('verify/listing/package/',   views.verify_payment, name='verify_payment'),

    # ── Boost actions ─────────────────────────────────────────────────────────
    # Manual push-up (spends one manual_boosts_remaining credit)
    path(
        'boost/manual/<slug:property_slug>/',
        views.manual_boost,
        name='manual_boost'
    ),

    # Premium tier upgrade (spends a premium / premium_gold / sponsored credit)
    # tier choices: premium | premium_gold | sponsored
    path(
        'boost/tier/<slug:property_slug>/<str:tier>/',
        views.apply_premium_tier,
        name='apply_premium_tier'
    ),

    # ── Location APIs ─────────────────────────────────────────────────────────
    path('api/states/',               views.get_states_api, name='api_states'),
    path('api/cities/',               views.get_cities_by_state, name='api_cities'),
]