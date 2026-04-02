from django.shortcuts import render, redirect
from django.contrib import messages
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.mail import send_mail, EmailMultiAlternatives, BadHeaderError
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime
from .models import ContactMessage, Newsletter, ContactInfo


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class ContactView(TemplateView):
    """Main contact page view"""
    template_name = 'estate/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get active contact information
        contact_info = ContactInfo.get_active()
        context['contact_info'] = contact_info
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle contact form submission"""
        
        # Get form data
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()
        
        # Validation
        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if not subject:
            errors.append("Subject is required.")
        if not message_text:
            errors.append("Message is required.")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return self.get(request, *args, **kwargs)
        
        try:
            # Create contact message
            contact_message = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message_text,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            # Send notification email to admin
            try:
                admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
                contact_info = ContactInfo.get_active()
                
                # Prepare context for email template
                email_context = {
                    'name': name,
                    'email': email,
                    'subject': subject,
                    'message': message_text,
                    'submitted_at': contact_message.created_at,
                    'ip_address': contact_message.ip_address,
                    'site_name': contact_info.company_name if contact_info else 'Nestova',
                    'admin_url': request.build_absolute_uri('/admin/contact/contactmessage/'),
                    'current_year': datetime.now().year,
                }
                
                # Render HTML email
                html_message = render_to_string('emails/contact_admin_notification.html', email_context)
                plain_message = strip_tags(html_message)
                
                # Send email with HTML
                msg = EmailMultiAlternatives(
                    subject=f"New Contact Message: {subject}",
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[admin_email]
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except (BadHeaderError, Exception) as e:
                # Log error but don't fail the submission
                print(f"Error sending notification email: {e}")
            
            # Send confirmation email to user
            try:
                contact_info = ContactInfo.get_active()
                
                # Prepare context for email template
                email_context = {
                    'name': name,
                    'email': email,
                    'subject': subject,
                    'message': message_text,
                    'submitted_at': contact_message.created_at,
                    'site_name': contact_info.company_name if contact_info else 'Nestova',
                    'contact_phone': contact_info.phone if contact_info else None,
                    'contact_email': contact_info.email if contact_info else None,
                    'contact_address': contact_info.get_full_address() if contact_info else None,
                    'current_year': datetime.now().year,
                    'social_links': {
                        'facebook': contact_info.facebook_url if contact_info else None,
                        'twitter': contact_info.twitter_url if contact_info else None,
                        'linkedin': contact_info.linkedin_url if contact_info else None,
                        'instagram': contact_info.instagram_url if contact_info else None,
                    } if contact_info else None,
                }
                
                # Render HTML email
                html_message = render_to_string('emails/contact_user_confirmation.html', email_context)
                plain_message = strip_tags(html_message)
                
                # Send email with HTML
                msg = EmailMultiAlternatives(
                    subject="Thank you for contacting us",
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email]
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except (BadHeaderError, Exception) as e:
                print(f"Error sending confirmation email: {e}")
            
            messages.success(request, "Your message has been sent successfully! We'll get back to you soon.")
            return redirect('contact')
            
        except Exception as e:
            messages.error(request, "An error occurred while sending your message. Please try again.")
            print(f"Error creating contact message: {e}")
            return self.get(request, *args, **kwargs)


class NewsletterSubscribeView(View):
    """Handle newsletter subscription"""
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, "Email address is required.")
            return redirect('contact')
        
        try:
            # Check if already subscribed
            newsletter, created = Newsletter.objects.get_or_create(
                email=email,
                defaults={
                    'ip_address': get_client_ip(request),
                    'is_active': True
                }
            )
            
            if not created:
                if newsletter.is_active:
                    messages.info(request, "You're already subscribed to our newsletter!")
                else:
                    # Reactivate subscription
                    newsletter.is_active = True
                    newsletter.unsubscribed_at = None
                    newsletter.save()
                    messages.success(request, "Welcome back! Your subscription has been reactivated.")
            else:
                # Send welcome email
                try:
                    contact_info = ContactInfo.get_active()
                    
                    # Prepare context for email template
                    email_context = {
                        'site_name': contact_info.company_name if contact_info else 'Nestova',
                        'site_url': request.build_absolute_uri('/'),
                        'unsubscribe_url': request.build_absolute_uri('/newsletter/unsubscribe/'),
                        'contact_email': contact_info.email if contact_info else None,
                        'contact_address': contact_info.get_full_address() if contact_info else None,
                        'current_year': datetime.now().year,
                        'social_links': {
                            'facebook': contact_info.facebook_url if contact_info else None,
                            'twitter': contact_info.twitter_url if contact_info else None,
                            'linkedin': contact_info.linkedin_url if contact_info else None,
                            'instagram': contact_info.instagram_url if contact_info else None,
                        } if contact_info else None,
                    }
                    
                    # Render HTML email
                    html_message = render_to_string('emails/newsletter_welcome.html', email_context)
                    plain_message = strip_tags(html_message)
                    
                    # Send email with HTML
                    msg = EmailMultiAlternatives(
                        subject="Welcome to our Newsletter",
                        body=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[email]
                    )
                    msg.attach_alternative(html_message, "text/html")
                    msg.send(fail_silently=True)
                except Exception as e:
                    print(f"Error sending welcome email: {e}")
                
                messages.success(request, "Thank you for subscribing! Check your email for confirmation.")
            
            return redirect('contact')
            
        except IntegrityError:
            messages.error(request, "This email is already subscribed.")
            return redirect('contact')
        except Exception as e:
            messages.error(request, "An error occurred. Please try again.")
            print(f"Error subscribing to newsletter: {e}")
            return redirect('contact')


class ContactMessageAjaxView(View):
    """Handle AJAX contact form submission"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle AJAX POST request"""
        
        # Get form data
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()
        
        # Validation
        if not all([name, email, subject, message_text]):
            return JsonResponse({
                'success': False,
                'message': 'All fields are required.'
            }, status=400)
        
        try:
            # Create contact message
            contact_message = ContactMessage.objects.create(
                name=name,
                email=email,
                subject=subject,
                message=message_text,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )
            
            # Send notification email
            try:
                admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
                contact_info = ContactInfo.get_active()
                
                # Prepare context for email template
                email_context = {
                    'name': name,
                    'email': email,
                    'subject': subject,
                    'message': message_text,
                    'submitted_at': contact_message.created_at,
                    'ip_address': contact_message.ip_address,
                    'site_name': contact_info.company_name if contact_info else 'Nestova',
                    'admin_url': request.build_absolute_uri('/admin/contact/contactmessage/'),
                    'current_year': datetime.now().year,
                }
                
                # Render HTML email
                html_message = render_to_string('emails/contact_admin_notification.html', email_context)
                plain_message = strip_tags(html_message)
                
                # Send email with HTML
                msg = EmailMultiAlternatives(
                    subject=f"New Contact Message: {subject}",
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[admin_email]
                )
                msg.attach_alternative(html_message, "text/html")
                msg.send(fail_silently=True)
            except Exception as e:
                print(f"Error sending email: {e}")
            
            return JsonResponse({
                'success': True,
                'message': 'Your message has been sent successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'An error occurred. Please try again.'
            }, status=500)


class NewsletterAjaxView(View):
    """Handle AJAX newsletter subscription"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip()
        
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Email address is required.'
            }, status=400)
        
        try:
            newsletter, created = Newsletter.objects.get_or_create(
                email=email,
                defaults={
                    'ip_address': get_client_ip(request),
                    'is_active': True
                }
            )
            
            if not created and newsletter.is_active:
                return JsonResponse({
                    'success': False,
                    'message': "You're already subscribed!"
                })
            
            if not created and not newsletter.is_active:
                newsletter.is_active = True
                newsletter.unsubscribed_at = None
                newsletter.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Thank you for subscribing!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'An error occurred. Please try again.'
            }, status=500)