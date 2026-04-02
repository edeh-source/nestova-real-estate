# agents/utils.py
"""Helper functions for agent referral tracking"""

from .models import Agent


def get_referring_agent_from_session(request):
    """
    Get referring agent from session if exists
    Returns Agent object or None
    """
    referral_code = request.session.get('agent_referral')
    if referral_code:
        try:
            agent = Agent.objects.get(referral_code=referral_code, is_active=True)
            return agent
        except Agent.DoesNotExist:
            return None
    return None


def store_property_referral(request, property_id, agent_code):
    """
    Store property-specific referral in session
    Format: property_ref_{property_id} = agent_code
    """
    session_key = f'property_ref_{property_id}'
    request.session[session_key] = agent_code
    request.session.set_expiry(2592000)  # 30 days


def get_property_referring_agent(request, property_id):
    """
    Get referring agent for a specific property
    Checks both property-specific and general referral
    """
    # First check property-specific referral
    session_key = f'property_ref_{property_id}'
    agent_code = request.session.get(session_key)
    
    if not agent_code:
        # Fall back to general agent referral
        agent_code = request.session.get('agent_referral')
    
    if agent_code:
        try:
            agent = Agent.objects.get(referral_code=agent_code, is_active=True)
            return agent
        except Agent.DoesNotExist:
            return None
    return None


def generate_property_referral_url(request, property, agent):
    """
    Generate referral URL for a property with agent's referral code
    """
    from django.urls import reverse
    property_url = request.build_absolute_uri(
        reverse('property_detail', kwargs={'slug': property.slug})
    )
    return f"{property_url}?ref={agent.referral_code}"


def clear_property_referral(request, property_id):
    """Clear property-specific referral from session"""
    session_key = f'property_ref_{property_id}'
    if session_key in request.session:
        del request.session[session_key]
