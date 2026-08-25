from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.views.decorators.csrf import ensure_csrf_cookie
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render

from django.views.decorators.csrf import csrf_exempt
import json
from .tasks import send_password_reset_email_task

# Get the User model (works with custom user models too)


User = get_user_model()
# Create your views here.



def register_page(request):
    """
    A method to register a user with account type selection

    Args:
        request (_type_): _description_

    Returns:
        _type_: _description_
    """
    if request.method == "POST":
        username = request.POST.get("username", None).strip()
        email = request.POST.get("email", None).strip()
        phone_number = request.POST.get("phone_number", None).strip()
        password = request.POST.get("password", None).strip()
        confirm_password = request.POST.get("confirm_password", None).strip()
        account_type = request.POST.get("account_type", "user").strip()
    
        if User.objects.filter(username=username).exists():
            return JsonResponse({
                "status": "error",
                "message": "Username Already Taken",
            })
        
        if User.objects.filter(email=email).exists():
            return JsonResponse({
            "status": "error",
            "message": "Email Already Taken",
            })
        
        
        if User.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({
            "status": "error",
            "message": "Phone Number Already In Use",
            })
        
        
        if len(password) <=5 :
            return JsonResponse({
            "status": "error",
            "message": "Password Too Short"
            })   
        
    
        if password != confirm_password:
            return JsonResponse({
            "status": "error",
            "message": "Passwords Are Not Matching"
            })    
        
        
        # Create user with account type
        user = User.objects.create_user(
            username=username, 
            email=email, 
            phone_number=phone_number, 
            password=password,
            account_type=account_type
        )
        
        if user:
            # Handle account type specific setup
            if account_type == 'agent':
                # Create agent profile
                from agents.models import Agent, Bank
                
                bank_id = request.POST.get("bank")
                account_name = request.POST.get('account_name')
                account_number = request.POST.get('account_number')
                upline_code = request.POST.get('upline_code')
                
                upline = None 
                if upline_code:
                    try:
                        upline = Agent.objects.get(referral_code=upline_code)
                    except Agent.DoesNotExist:
                        pass
                
                bank = None
                if bank_id:
                    try:
                        bank = Bank.objects.get(id=bank_id)
                    except Bank.DoesNotExist:
                        pass
                
                # Create agent profile
                Agent.objects.create(
                    user=user, 
                    upline=upline, 
                    bank=bank, 
                    account_name=account_name, 
                    account_number=account_number, 
                    bank_verified=False
                )
                
                # Update user flags
                user.is_agent = True
                user.save()
                
            elif account_type == 'company':
                # Create company profile
                from agents.models import Company
                
                company_name = request.POST.get('company_name')
                registration_number = request.POST.get('registration_number', '')
                company_email = request.POST.get('company_email', '')
                company_phone = request.POST.get('company_phone', '')
                company_address = request.POST.get('company_address', '')
                
                # Create company profile
                Company.objects.create(
                    user=user,
                    company_name=company_name,
                    registration_number=registration_number,
                    company_email=company_email if company_email else None,
                    company_phone=company_phone if company_phone else None,
                    address=company_address if company_address else None,
                )
                
                # Update user flags
                user.is_company = True
                user.save()
            
            # Check for referring agent (for normal users)
            if account_type == 'user':
                referral_code = request.session.get('agent_referral')
                if referral_code:
                    try:
                        from agents.models import Agent
                        from shop.models import CustomerProfile
                        
                        referring_agent = Agent.objects.get(referral_code=referral_code, is_active=True)
                        profile, created = CustomerProfile.objects.get_or_create(user=user)
                        profile.referred_by = referring_agent
                        profile.save()
                    except Exception as e:
                        # Don't fail registration if referral tracking fails
                        print(f"Referral tracking error: {e}")
            
            return JsonResponse({
            "status": "success",
            "message": "Account Created Successfully!",
            "redirect_url": reverse("users:login")
            })    
    else:
        # Get banks for agent signup
        from agents.models import Bank
        banks = Bank.objects.filter(is_active=True)
        
        # Check for upline referral code
        upline_code = request.GET.get('ref')
        upline_agent = None
        if upline_code:
            try:
                from agents.models import Agent
                upline_agent = Agent.objects.get(referral_code=upline_code)
            except:
                upline_agent = None
        
        return render(request, "users/signup.html", {
            "banks": banks,
            "upline_code": upline_code,
            "upline_agent": upline_agent,
        })

        
    


@ensure_csrf_cookie
def login__page(request):
    """
    A method to login in a user

    Args:
        request (_type_): _description_

    Returns:
        _type_: _description_
    """
    if request.user.is_authenticated and request.path == '/login/':
        return redirect("home")
    else:
        pass
        if request.method == "POST":
            identifier = request.POST.get("email_or_phone", None).strip()
            password = request.POST.get("password", None).strip()
            user = authenticate(request, identifier=identifier, password=password)
            if user is not None:
                if user.is_active:
                    login(request, user)
                    
                    # Check if there's a 'next' parameter in the request
                    # This is where the user was trying to go before being asked to login
                    next_url = request.GET.get('next') or request.POST.get('next')
                    
                    # If there's a next URL, redirect there. Otherwise, go to dashboard
                    if next_url:
                        redirect_url = next_url
                    else:
                        redirect_url = reverse("shop:profile")
                    
                    return JsonResponse({
                    'status': "success",
                    "message": "Logged In Successfully ",
                    "redirect_url": redirect_url
                    })
                
                else:
                    return JsonResponse({
                    "status": "error",
                    "message": "Account Not Active"
                    })
                
            else:
                return JsonResponse({
                "status": "error",
                "message": "Credentials Does Not Exist"
                })
            
        else:
            return render(request, "estate/login.html")  
        
                      
                
                
                
                
def users__dashboard(request, username):
    return render(request, "estate/dashboard.html", {"username": username})     



def users_logout(request):
    """
    A method to log out a user out
    """   
    logout(request)
    messages.success(request, "Logged Out Successfully")
    return redirect("users:login")    
    
    
    
# views.py



# VIEW 1: Password Reset Request Page
def password_reset_request(request):
    """
    This view handles the initial password reset request.
    It displays a form where users enter their email/phone.
    """
    if request.method == 'POST':
        # Get the email or phone from the form
        email_or_phone = request.POST.get('email_or_phone')
        
        # Try to find user by email first
        try:
            user = User.objects.get(email=email_or_phone)
        except User.DoesNotExist:
            # If not found by email, try phone number
            try:
                user = User.objects.get(phone=email_or_phone)
            except User.DoesNotExist:
                # User not found, but we don't tell them for security
                return JsonResponse({
                    'status': 'success',
                    'message': 'If an account exists, a reset link has been sent.'
                })
        
        # Generate a unique token for this user
        # This token is tied to the user's password, so it becomes invalid after password change
        token = default_token_generator.make_token(user)
        
        # Encode the user's ID in base64 for URL safety
        # force_bytes() converts the ID to bytes, urlsafe_base64_encode() makes it URL-safe
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        # Build the password reset link
        # This link will be sent to the user's email
        reset_link = request.build_absolute_uri(
            f'/password-reset-confirm/{uid}/{token}/'
        )
        
        # Send the email asynchronously via Celery
        try:
            send_password_reset_email_task.delay(user.email, user.first_name, reset_link)
            return JsonResponse({
                'status': 'success',
                'message': 'Password reset link has been sent to your email.'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to dispatch email task. Please try again later.'
            })
    
    # If GET request, just show the form
    return render(request, 'estate/password_reset_request.html')


# VIEW 2: Password Reset Confirm Page
def password_reset_confirm(request, uidb64, token):
    """
    This view handles the password reset confirmation.
    Users arrive here after clicking the link in their email.
    """
    # Decode the user ID from base64
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    
    # Check if the token is valid for this user
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            # Get the new password from the form
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            # Validate passwords match
            if password1 != password2:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Passwords do not match.'
                })
            
            # Validate password length
            if len(password1) < 8:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Password must be at least 8 characters long.'
                })
            
            # Set the new password
            # set_password() hashes the password before saving
            user.set_password(password1)
            user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Password has been reset successfully.',
                'redirect_url': '/login/'
            })
        
        # If GET request, show the password reset form
        return render(request, 'estate/password_reset_confirm.html', {
            'validlink': True,
            'uidb64': uidb64,
            'token': token
        })
    else:
        # Invalid or expired token
        return render(request, 'estate/password_reset_confirm.html', {
            'validlink': False
        })




@login_required
def submit_user_verification(request):
    """Normal user submits NIN/vNIN/BVN verification to post properties"""
    if request.user.id_verified and request.user.can_post_properties:
        messages.info(request, "You are already verified and can post properties.")
        return redirect('shop:profile')

    # Context shared by both GET and error re-renders
    ctx = {
        'user': request.user,
        # Pre-fill name fields from user model if available
        'prefill_first_name': request.user.first_name or '',
        'prefill_last_name': request.user.last_name or '',
    }

    if request.method == 'POST':
        from django.utils import timezone
        from agents.verification_service import VerificationService

        id_type      = request.POST.get('id_type', '').strip()
        id_number    = request.POST.get('id_number', '').strip()
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        date_of_birth = request.POST.get('date_of_birth', '').strip()

        # Preserve all field values so the form re-fills on error
        ctx.update({
            'id_type':      id_type,
            'id_number':    id_number,
            'first_name':   first_name,
            'last_name':    last_name,
            'date_of_birth': date_of_birth,
        })

        # ── Basic validation ────────────────────────────────────────
        if not id_type or not id_number:
            ctx['error'] = "Please provide both ID type and ID number."
            return render(request, 'users/submit_user_verification.html', ctx)

        if id_type not in ('nin', 'vnin', 'bvn'):
            ctx['error'] = "Invalid ID type selected. Choose NIN, vNIN, or BVN."
            return render(request, 'users/submit_user_verification.html', ctx)

        if not first_name or not last_name:
            ctx['error'] = "Please enter your first name and last name exactly as they appear on your ID."
            return render(request, 'users/submit_user_verification.html', ctx)

        # ── Persist what was submitted ──────────────────────────────
        request.user.id_type = id_type
        request.user.id_number = id_number
        # Update name on user model if not already set
        if not request.user.first_name:
            request.user.first_name = first_name
        if not request.user.last_name:
            request.user.last_name = last_name
        request.user.save()

        # ── Call Dojah API ──────────────────────────────────────────
        service = VerificationService()
        try:
            if id_type == 'nin':
                success, result = service.verify_nin(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None,
                )
            elif id_type == 'vnin':
                success, result = service.verify_vnin(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None,
                )
            else:  # bvn
                success, result = service.verify_bvn(
                    request.user, id_number,
                    first_name=first_name, last_name=last_name, dob=date_of_birth or None,
                )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            ctx['error'] = f"An unexpected error occurred while contacting the verification service: {exc}"
            return render(request, 'users/submit_user_verification.html', ctx)

        # ── API returned failure ────────────────────────────────────
        if not success:
            error_msg = result if isinstance(result, str) else "Verification failed. Please try again."
            ctx['error'] = f"Verification failed: {error_msg}"
            return render(request, 'users/submit_user_verification.html', ctx)

        # ── API succeeded — evaluate confidence ────────────────────
        try:
            confidence_result = result['confidence']

            request.user.verification_data = {
                'api_response': result,
                'confidence_score': confidence_result['overall_confidence'],
                'confidence_breakdown': confidence_result['breakdown'],
                'verified_at': timezone.now().isoformat(),
                'submitted': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'date_of_birth': date_of_birth,
                    'id_type': id_type,
                }
            }

            overall_confidence = float(confidence_result.get('overall_confidence', 0))
            recommendation     = confidence_result.get('recommendation', 'auto_reject')

            if recommendation == 'auto_approve' or overall_confidence >= 85:
                request.user.id_verified = True
                request.user.can_post_properties = True
                request.user.id_verification_date = timezone.now()
                request.user.verification_status = 'verified'
                request.user.save()

                if hasattr(request.user, 'agent_profile'):
                    agent = request.user.agent_profile
                    agent.can_post_properties = True
                    agent.id_verified = True
                    agent.id_verification_date = timezone.now()
                    agent.verification_status = 'verified'
                    agent.save()

                messages.success(
                    request,
                    f"✅ Verification successful! Your identity has been verified "
                    f"with {overall_confidence:.0f}% confidence. You can now post properties."
                )
                return redirect('shop:profile')

            elif recommendation == 'manual_review' or overall_confidence >= 70:
                request.user.id_verified = True
                request.user.can_post_properties = True
                request.user.id_verification_date = timezone.now()
                request.user.verification_status = 'in_review'
                request.user.save()

                if hasattr(request.user, 'agent_profile'):
                    agent = request.user.agent_profile
                    agent.can_post_properties = True
                    agent.id_verified = True
                    agent.id_verification_date = timezone.now()
                    agent.verification_status = 'in_review'
                    agent.save()

                messages.info(
                    request,
                    f"⏳ Your verification is under review (confidence: {overall_confidence:.0f}%). "
                    "You can now post properties while our team completes the background review."
                )
                return redirect('shop:profile')

            else:  # auto_reject
                request.user.id_verified = False
                request.user.can_post_properties = False
                request.user.verification_status = 'rejected'
                request.user.save()

                if hasattr(request.user, 'agent_profile'):
                    agent = request.user.agent_profile
                    agent.can_post_properties = False
                    agent.id_verified = False
                    agent.verification_status = 'rejected'
                    agent.save()
                breakdown = confidence_result.get('breakdown', {})
                failed_fields = [
                    k.replace('_', ' ').title()
                    for k, v in breakdown.items()
                    if isinstance(v, dict) and v.get('score', 100) < 60
                ]
                hint = (
                    f" Fields that didn't match: {', '.join(failed_fields)}."
                    if failed_fields else ""
                )
                ctx['error'] = (
                    f"❌ Verification failed (confidence: {overall_confidence:.0f}%). "
                    f"The details you entered do not match the records for this {id_type.upper()}.{hint} "
                    "Please double-check your name and date of birth and try again."
                )
                return render(request, 'users/submit_user_verification.html', ctx)

        except Exception as e:
            import traceback
            traceback.print_exc()
            ctx['error'] = f"Verification processing error: {str(e)}"
            return render(request, 'users/submit_user_verification.html', ctx)

    # GET request — show the form
    return render(request, 'users/submit_user_verification.html', ctx)