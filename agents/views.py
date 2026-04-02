from django.shortcuts import render, redirect
from .models import Agent
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth import login
from .models import Bank
from django.http import JsonResponse
from .models import Agent
from django.contrib import messages
from django.urls import reverse


User = get_user_model()


# Helper function to use in views
def agent_required(view_func):
    """Decorator to ensure user is an agent"""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'agent_profile'):
            messages.error(request, 'You must be an agent to access this page')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper

# Usage:
from django.contrib.auth.decorators import login_required

@login_required
@agent_required
def agent_dashboard(request):
    """Only agents can access this"""
    agent = request.user.agent_profile
    return render(request, 'agents/dashboard.html', {'agent': agent})


def agents_signup(request):
    """
    A method to signup for an agent
    Redirects to unified signup with agent type pre-selected
    """
    # If user is already logged in and wants to upgrade to agent
    if request.user.is_authenticated:
        if Agent.objects.filter(user=request.user).exists():
            messages.info(request, "You are already an agent")
            return redirect('shop:profile')
        
        # Allow logged-in users to upgrade to agent
        banks = Bank.objects.all()
        if request.method == "POST":
            bank_id = request.POST.get("bank")
            account_name = request.POST.get('account_name')
            account_number = request.POST.get('account_number')
            upline_code = request.POST.get('upline_code') or request.GET.get('ref')
            upline = None 
            if upline_code:
                try:
                    upline = Agent.objects.get(referral_code=upline_code)
                except Agent.DoesNotExist:
                    messages.warning(request, 'Invalid referral code, registered without upline')
                    
            if bank_id:
                try:
                    bank = Bank.objects.get(id=bank_id)
                except Bank.DoesNotExist:
                    pass
                
            agent = Agent.objects.create(user=request.user, upline=upline, bank=bank, account_name=account_name, account_number=account_number, bank_verified=False)
            try:
                user = User.objects.get(username=agent.user.username)
                user.is_agent = True
                user.account_type = 'agent'
                user.save()
            except User.DoesNotExist:
                return JsonResponse({
                    "status": "error",
                    "message": "User Does Not Exist"
                })    
            return JsonResponse({
                "status": "success",
                "message": "Agent Profile Created Successfully",
                "redirect_url": reverse("shop:profile")
            })
        else:
            upline_code = request.GET.get('ref')
            upline_agent = None
            if upline_code:
                try:
                    upline_agent = Agent.objects.get(referral_code=upline_code)
                except Agent.DoesNotExist:
                    upline_agent = None
            return render(request, "agents/signup.html", {"banks": banks, 'upline_code': upline_code, 'upline_agent': upline_agent,})
    else:
        # Redirect to unified signup with agent type pre-selected
        upline_code = request.GET.get('ref', '')
        if upline_code:
            return redirect(f"{reverse('users:register')}?type=agent&ref={upline_code}")
        return redirect(f"{reverse('users:register')}?type=agent")

# Helper function for companies
def company_required(view_func):
    """Decorator to ensure user is a company"""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'company_profile'):
            messages.error(request, 'You must be a company to access this page')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
def verification_dashboard(request):
    """General verification status page for agents and companies"""
    context = {
        'agent': None,
        'company': None,
        'user_type': None
    }
    
    if hasattr(request.user, 'agent_profile'):
        context['agent'] = request.user.agent_profile
        context['user_type'] = 'agent'
    elif hasattr(request.user, 'company_profile'):
        context['company'] = request.user.company_profile
        context['user_type'] = 'company'
    else:
        messages.warning(request, "You don't have an agent or company profile to verify.")
        return redirect('shop:profile')
        
    return render(request, 'agents/verification_dashboard.html', context)

@login_required
@agent_required
def submit_agent_verification(request):
    """Agent submits identity verification details with automatic verification"""
    agent = request.user.agent_profile
    if agent.verification_status == 'verified':
        messages.info(request, "You are already verified.")
        return redirect('agents:verification_dashboard')

    if request.method == 'POST':
        from django.utils import timezone
        from .verification_service import VerificationService
        
        id_type = request.POST.get('id_type')
        id_number = request.POST.get('id_number')
        id_card_front = request.FILES.get('id_card_front')
        id_card_back = request.FILES.get('id_card_back')
        selfie = request.FILES.get('selfie')

        # Save documents
        agent.id_type = id_type
        agent.id_number = id_number
        if id_card_front: agent.id_card_front = id_card_front
        if id_card_back: agent.id_card_back = id_card_back
        if selfie: agent.selfie_photo = selfie
        
        agent.verification_status = 'in_review'
        agent.save()

        # AUTOMATIC VERIFICATION with confidence scoring
        service = VerificationService()
        verification_success = False
        api_data = {}
        
        # Try verification based on ID type
        if id_type == 'nin' and id_number:
            success, result = service.verify_nin(request.user, id_number)
            if success:
                verification_success = True
                api_data = result
                agent.id_verified = True
        
        elif id_type == 'vnin' and id_number:
            success, result = service.verify_vnin(request.user, id_number)
            if success:
                verification_success = True
                api_data = result
                agent.id_verified = True
        
        elif id_type == 'bvn' and id_number:
            success, result = service.verify_bvn(request.user, id_number)
            if success:
                verification_success = True
                api_data = result
                agent.id_verified = True
        
        # Calculate confidence score if verification succeeded
        if verification_success and api_data:
            confidence_result = service.calculate_confidence_score(api_data, request.user, agent)
            
            # Store verification data
            agent.verification_data = {
                'api_response': api_data,
                'confidence_score': confidence_result['overall_confidence'],
                'confidence_breakdown': confidence_result['breakdown'],
                'checks_performed': confidence_result['checks_performed'],
                'verified_at': timezone.now().isoformat()
            }
            
            overall_confidence = confidence_result['overall_confidence']
            recommendation = confidence_result['recommendation']
            
            # Auto-approve if confidence is high enough
            if recommendation == 'auto_approve':
                agent.verification_status = 'verified'
                agent.can_post_properties = True
                agent.verified_at = timezone.now()
                agent.save()
                
                messages.success(
                    request, 
                    f"✅ Verification successful! Your identity has been verified with {overall_confidence:.0f}% confidence. "
                    "You can now post properties."
                )
                
                # TODO: Send approval email notification
                # from .notifications import notify_verification_approved
                # notify_verification_approved(request.user, 'agent')
                
                return redirect('agents:verification_dashboard')
            
            # Manual review for medium confidence
            elif recommendation == 'manual_review':
                agent.verification_status = 'in_review'
                agent.save()
                
                messages.info(
                    request,
                    f"⏳ Your verification is under review (confidence: {overall_confidence:.0f}%). "
                    "Our team will review your documents and notify you within 24-48 hours."
                )
                
                return redirect('agents:verification_dashboard')
            
            # Auto-reject for low confidence
            else:
                agent.verification_status = 'rejected'
                agent.rejection_reason = (
                    f"Automatic verification failed due to low confidence score ({overall_confidence:.0f}%). "
                    "Please ensure your information matches your ID document exactly and try again."
                )
                agent.save()
                
                messages.error(
                    request,
                    f"❌ Verification failed. The information provided does not match our records "
                    f"(confidence: {overall_confidence:.0f}%). Please check your details and try again."
                )
                
                return redirect('agents:verification_dashboard')
        
        else:
            # API verification failed - send to manual review
            agent.verification_status = 'in_review'
            agent.save()
            
            messages.info(
                request,
                "⏳ Your verification documents have been submitted and are under review. "
                "We'll notify you once the review is complete."
            )
            
            return redirect('agents:verification_dashboard')

    return render(request, 'agents/submit_agent_verification.html', {'agent': agent})

@login_required
@company_required
def submit_company_verification(request):
    """Company submits business verification details with automatic CAC verification"""
    company = request.user.company_profile
    if company.verification_status == 'verified':
        messages.info(request, "Your company is already verified.")
        return redirect('agents:verification_dashboard')

    if request.method == 'POST':
        from django.utils import timezone
        from .verification_service import VerificationService
        
        rc_number = request.POST.get('rc_number')
        cac_cert = request.FILES.get('cac_certificate')
        utility_bill = request.FILES.get('utility_bill')

        # Save documents
        company.rc_number = rc_number
        if cac_cert: company.cac_certificate = cac_cert
        if utility_bill: company.utility_bill = utility_bill
        
        company.verification_status = 'in_review'
        company.save()

        # AUTOMATIC CAC VERIFICATION
        if rc_number:
            service = VerificationService()
            success, result = service.verify_cac(request.user, rc_number, company.company_name)
            
            if success:
                company.cac_verified = True
                company.cac_verification_date = timezone.now()
                
                # Calculate confidence based on company name matching
                api_company_name = result.get('company_name') or result.get('name', '')
                
                if api_company_name:
                    # Fuzzy match company names
                    name_match_score = service._fuzzy_match_name(api_company_name, company.company_name)
                    
                    # Store verification data
                    company.cac_data = {
                        'api_response': result,
                        'name_match_score': name_match_score,
                        'verified_at': timezone.now().isoformat()
                    }
                    
                    # Auto-approve if name match is strong (90%+)
                    if name_match_score >= 90:
                        company.verification_status = 'verified'
                        company.can_post_properties = True
                        company.is_verified = True
                        company.verified_at = timezone.now()
                        company.save()
                        
                        messages.success(
                            request,
                            f"✅ Company verification successful! Your CAC registration has been verified "
                            f"with {name_match_score:.0f}% name match. You can now post properties."
                        )
                        
                        # TODO: Send approval email notification
                        # from .notifications import notify_verification_approved
                        # notify_verification_approved(request.user, 'company')
                        
                        return redirect('agents:verification_dashboard')
                    
                    # Manual review for medium confidence (70-90%)
                    elif name_match_score >= 70:
                        company.verification_status = 'in_review'
                        company.save()
                        
                        messages.info(
                            request,
                            f"⏳ Your company verification is under review (name match: {name_match_score:.0f}%). "
                            "Our team will review your documents and notify you within 24-48 hours."
                        )
                        
                        return redirect('agents:verification_dashboard')
                    
                    # Auto-reject for low confidence
                    else:
                        company.verification_status = 'rejected'
                        company.rejection_reason = (
                            f"Company name mismatch. CAC records show '{api_company_name}' "
                            f"but your profile shows '{company.company_name}'. "
                            f"Please update your company name to match CAC records."
                        )
                        company.save()
                        
                        messages.error(
                            request,
                            f"❌ Verification failed. Company name mismatch detected "
                            f"(match: {name_match_score:.0f}%). Please ensure your company name "
                            "matches your CAC registration exactly."
                        )
                        
                        return redirect('agents:verification_dashboard')
                else:
                    # CAC verified but no name in response - manual review
                    company.verification_status = 'in_review'
                    company.save()
                    
                    messages.info(
                        request,
                        "⏳ Your CAC registration has been verified. Our team will review your "
                        "documents and notify you within 24-48 hours."
                    )
                    
                    return redirect('agents:verification_dashboard')
            else:
                # CAC verification failed - send to manual review
                company.verification_status = 'in_review'
                company.save()
                
                messages.info(
                    request,
                    "⏳ Your company verification documents have been submitted and are under review. "
                    "We'll notify you once the review is complete."
                )
                
                return redirect('agents:verification_dashboard')
        else:
            # No RC number provided - manual review
            company.verification_status = 'in_review'
            company.save()
            
            messages.info(
                request,
                "⏳ Your company verification documents have been submitted and are under review."
            )
            
            return redirect('agents:verification_dashboard')

    return render(request, 'agents/submit_company_verification.html', {'company': company})


def agent_profile(request, slug):
    """Display agent profile with their properties"""
    from django.shortcuts import get_object_or_404
    from property.models import Property
    
    agent = get_object_or_404(Agent, slug=slug)
    
    # Get recent properties by this agent (limit to 6 for profile page)
    recent_properties = Property.objects.filter(
        agent=agent,
        is_active=True
    ).select_related('state', 'city', 'property_type', 'status').order_by('-created_at')[:6]
    
    # Get agent statistics
    total_properties = Property.objects.filter(agent=agent, is_active=True).count()
    
    context = {
        'agent': agent,
        'recent_properties': recent_properties,
        'total_properties': total_properties,
    }
    
    return render(request, 'agents/agent_profile_dynamic.html', context)


def agent_search_autocomplete(request):
    """AJAX autocomplete for agent search — returns JSON suggestions"""
    from django.db.models import Q, Count
    from property.models import Property

    query = request.GET.get('q', '').strip()
    results = []

    if len(query) >= 2:
        agents = (
            Agent.objects
            .filter(
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__username__icontains=query)
                )
            .select_related('user')[:8]
        )

        for agent in agents:
            full_name = (
                f"{agent.user.first_name} {agent.user.last_name}".strip()
                or agent.user.username
            )
            # Safely get optional fields
            avatar_url = None
            if hasattr(agent, 'avatar') and agent.avatar:
                try:
                    avatar_url = agent.avatar.url
                except Exception:
                    pass
            elif hasattr(agent, 'profile_picture') and agent.profile_picture:
                try:
                    avatar_url = agent.profile_picture.url
                except Exception:
                    pass

            results.append({
                'name': full_name,
                'slug': agent.slug,
                'url': reverse('agents:agent_profile', kwargs={'slug': agent.slug}),
                'avatar': avatar_url,
                'is_verified': agent.verification_status == 'verified',

            })

    return JsonResponse({'results': results})


def agent_search(request):
    """Full agent search results page"""
    from django.db.models import Q, Count
    from django.core.paginator import Paginator

    query = request.GET.get('q', '').strip()
    verified_only = request.GET.get('verified', '') == '1'

    agents_qs = Agent.objects.select_related('user')[:8]

    if query:
        agents_qs = agents_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) 
           
        )

    

    if verified_only:
        agents_qs = agents_qs.filter(verification_status='verified')

    paginator = Paginator(agents_qs, 12)
    page_number = request.GET.get('page')
    agents = paginator.get_page(page_number)

    context = {
        'agents': agents,
        'query': query,
        'verified_only': verified_only,
        'total': paginator.count,
    }
    return render(request, 'agents/agent_search.html', context)


def agent_properties(request, slug):
    """Display all properties listed by a specific agent"""
    from django.shortcuts import get_object_or_404
    from django.core.paginator import Paginator
    from property.models import Property
    
    agent = get_object_or_404(Agent, slug=slug)
    
    # Get all properties by this agent
    properties_list = Property.objects.filter(
        agent=agent,
        is_active=True
    ).select_related('state', 'city', 'property_type', 'status').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(properties_list, 12)  # 12 properties per page
    page_number = request.GET.get('page')
    properties = paginator.get_page(page_number)
    
    context = {
        'agent': agent,
        'properties': properties,
        'total_properties': properties_list.count(),
    }
    
    return render(request, 'agents/agent_properties.html', context)