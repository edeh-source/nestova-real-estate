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
        agent = request.user.agent_profile
        # Auto-heal: If confidence score was >= 70, ensure can_post_properties is True
        if isinstance(agent.verification_data, dict):
            score = agent.verification_data.get('confidence_score')
            if score is not None and float(score) >= 70:
                if not agent.can_post_properties or not agent.id_verified:
                    agent.can_post_properties = True
                    agent.id_verified = True
                    agent.save(update_fields=['can_post_properties', 'id_verified'])
                if not request.user.can_post_properties or not request.user.id_verified:
                    request.user.can_post_properties = True
                    request.user.id_verified = True
                    request.user.save(update_fields=['can_post_properties', 'id_verified'])
        context['agent'] = agent
        context['user_type'] = 'agent'
    elif hasattr(request.user, 'company_profile'):
        company = request.user.company_profile
        if isinstance(company.cac_data, dict):
            score = company.cac_data.get('name_match_score')
            if score is not None and float(score) >= 70:
                if not company.can_post_properties or not company.cac_verified:
                    company.can_post_properties = True
                    company.cac_verified = True
                    company.save(update_fields=['can_post_properties', 'cac_verified'])
                if not request.user.can_post_properties:
                    request.user.can_post_properties = True
                    request.user.save(update_fields=['can_post_properties'])
        context['company'] = company
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

    # Block re-submission if the agent already passed verification
    # (confidence ≥ 70 or can_post_properties is True) and status is not rejected
    if (agent.can_post_properties or agent.id_verified) and agent.verification_status != 'rejected':
        messages.info(
            request,
            "⏳ Your identity verification is already recorded and active. "
            "You cannot verify again unless an admin manually resets your verification status."
        )
        return redirect('agents:verification_dashboard')

    ctx = {
        'agent': agent,
        'prefill_first_name': agent.user.first_name or '',
        'prefill_last_name': agent.user.last_name or '',
    }

    if request.method == 'POST':
        from django.utils import timezone
        from .verification_service import VerificationService
        
        id_type = request.POST.get('id_type', '').strip()
        id_number = request.POST.get('id_number', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '').strip()
        id_card_front = request.FILES.get('id_card_front')
        id_card_back = request.FILES.get('id_card_back')
        selfie = request.FILES.get('selfie')

        # Preserve inputs for form re-fill
        ctx.update({
            'id_type': id_type,
            'id_number': id_number,
            'first_name': first_name,
            'last_name': last_name,
            'date_of_birth': date_of_birth,
        })

        # Basic validation
        if not id_type or not id_number:
            ctx['error'] = "Please provide both ID type and ID number."
            return render(request, 'agents/submit_agent_verification.html', ctx)

        if id_type in ('nin', 'vnin', 'bvn'):
            if not first_name or not last_name:
                ctx['error'] = "Please enter your first name and last name exactly as they appear on your ID."
                return render(request, 'agents/submit_agent_verification.html', ctx)

        # Save documents
        agent.id_type = id_type
        agent.id_number = id_number
        if id_card_front: agent.id_card_front = id_card_front
        if id_card_back: agent.id_card_back = id_card_back
        if selfie: agent.selfie_photo = selfie
        
        agent.verification_status = 'in_review'
        agent.save()

        # Update user names if not already set
        user = request.user
        if not user.first_name:
            user.first_name = first_name
        if not user.last_name:
            user.last_name = last_name
        user.save()

        # AUTOMATIC VERIFICATION with confidence scoring
        service = VerificationService()
        verification_success = False
        api_data = {}
        
        try:
            # Try verification based on ID type
            if id_type == 'nin' and id_number:
                success, result = service.verify_nin(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None
                )
                if success:
                    verification_success = True
                    api_data = result
            
            elif id_type == 'vnin' and id_number:
                success, result = service.verify_vnin(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None
                )
                if success:
                    verification_success = True
                    api_data = result
            
            elif id_type == 'bvn' and id_number:
                success, result = service.verify_bvn(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None
                )
                if success:
                    verification_success = True
                    api_data = result
        except Exception as e:
            import traceback
            traceback.print_exc()
            ctx['error'] = f"Verification processing error: {str(e)}"
            return render(request, 'agents/submit_agent_verification.html', ctx)
        
        # Calculate confidence score if verification succeeded
        if verification_success and api_data:
            confidence_result = service.calculate_confidence_score(
                api_data, request.user,
                submitted_first_name=first_name,
                submitted_last_name=last_name,
                submitted_dob=date_of_birth or None,
                user_profile=agent
            )
            
            overall_confidence = float(confidence_result.get('overall_confidence', 0))
            recommendation = confidence_result.get('recommendation', 'auto_reject')

            # Store verification data
            agent.verification_data = {
                'api_response': api_data,
                'confidence_score': overall_confidence,
                'confidence_breakdown': confidence_result.get('breakdown', {}),
                'checks_performed': confidence_result.get('checks_performed', 0),
                'verified_at': timezone.now().isoformat(),
                'submitted': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'date_of_birth': date_of_birth,
                    'id_type': id_type,
                }
            }
            
            # Confidence >= 85%: Auto-approve
            if recommendation == 'auto_approve' or overall_confidence >= 85:
                agent.verification_status = 'verified'
                agent.can_post_properties = True
                agent.id_verified = True
                agent.id_verification_date = timezone.now()
                agent.verified_at = timezone.now()
                agent.save()

                user = request.user
                user.can_post_properties = True
                user.id_verified = True
                user.id_verification_date = timezone.now()
                user.verification_status = 'verified'
                user.save()
                
                messages.success(
                    request, 
                    f"✅ Verification successful! Your identity has been verified with {overall_confidence:.0f}% confidence. "
                    "You can now post properties."
                )
                return redirect('agents:verification_dashboard')
            
            # Confidence 70% – 84%: Manual review path with UNLOCKED property posting
            elif recommendation == 'manual_review' or overall_confidence >= 70:
                agent.verification_status = 'in_review'
                agent.can_post_properties = True   # UNLOCK property posting since confidence >= 70
                agent.id_verified = True           # Mark passed so re-verification is blocked
                agent.id_verification_date = timezone.now()
                agent.save()

                user = request.user
                user.can_post_properties = True
                user.id_verified = True
                user.id_verification_date = timezone.now()
                user.verification_status = 'in_review'
                user.save()
                
                messages.info(
                    request,
                    f"⏳ Your verification is under review (confidence: {overall_confidence:.0f}%). "
                    "You can now post properties while our team completes the background review."
                )
                return redirect('agents:verification_dashboard')
            
            # Confidence < 70%: Auto-reject
            else:
                agent.verification_status = 'rejected'
                agent.can_post_properties = False
                agent.id_verified = False
                agent.rejection_reason = (
                    f"Automatic verification failed due to low confidence score ({overall_confidence:.0f}%). "
                    "Please ensure your information matches your ID document exactly and try again."
                )
                agent.save()

                user = request.user
                user.can_post_properties = False
                user.id_verified = False
                user.verification_status = 'rejected'
                user.save()
                
                messages.error(
                    request,
                    f"❌ Verification failed. The information provided does not match our records "
                    f"(confidence: {overall_confidence:.0f}%). Please check your details and try again."
                )
                return redirect('agents:verification_dashboard')
        
        else:
            # API verification failed or service unavailable - route to manual review (posting locked until reviewed)
            agent.verification_status = 'in_review'
            agent.can_post_properties = False
            agent.id_verified = False
            agent.save()
            
            messages.info(
                request,
                "⏳ Your verification documents have been submitted and are under review. "
                "We'll notify you once the review is complete."
            )
            return redirect('agents:verification_dashboard')

    return render(request, 'agents/submit_agent_verification.html', ctx)

@login_required
@company_required
def submit_company_verification(request):
    """Company submits business verification details with automatic CAC verification"""
    company = request.user.company_profile
    if company.verification_status == 'verified':
        messages.info(request, "Your company is already verified.")
        return redirect('agents:verification_dashboard')

    # Block re-submission if company already passed verification and is not rejected
    if (company.can_post_properties or company.cac_verified) and company.verification_status != 'rejected':
        messages.info(
            request,
            "⏳ Your company verification is already recorded. "
            "You cannot verify again unless an admin manually resets your status."
        )
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
                    name_match_score = float(service._fuzzy_match_name(api_company_name, company.company_name))
                    
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

                        user = request.user
                        user.can_post_properties = True
                        user.save()
                        
                        messages.success(
                            request,
                            f"✅ Company verification successful! Your CAC registration has been verified "
                            f"with {name_match_score:.0f}% name match. You can now post properties."
                        )
                        return redirect('agents:verification_dashboard')
                    
                    # Manual review for medium confidence (70-90%) - UNLOCK POSTING
                    elif name_match_score >= 70:
                        company.verification_status = 'in_review'
                        company.can_post_properties = True  # UNLOCK property posting for >= 70%
                        company.save()

                        user = request.user
                        user.can_post_properties = True
                        user.save()
                        
                        messages.info(
                            request,
                            f"⏳ Your company verification is under review (name match: {name_match_score:.0f}%). "
                            "You can now post properties while our team finalises the background review."
                        )
                        return redirect('agents:verification_dashboard')
                    
                    # Auto-reject for low confidence (< 70%)
                    else:
                        company.verification_status = 'rejected'
                        company.can_post_properties = False
                        company.rejection_reason = (
                            f"Company name mismatch. CAC records show '{api_company_name}' "
                            f"but your profile shows '{company.company_name}'. "
                            f"Please update your company name to match CAC records."
                        )
                        company.save()

                        user = request.user
                        user.can_post_properties = False
                        user.save()
                        
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
                company.can_post_properties = False
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
            company.can_post_properties = False
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
    
    lister_user = agent.user
    user_name = lister_user.get_full_name() or lister_user.username
    
    context = {
        'agent': agent,
        'lister_user': lister_user,
        'user_name': user_name,
        'properties': properties,
        'total_properties': properties_list.count(),
    }
    
    return render(request, 'agents/agent_properties.html', context)