from celery import shared_task
from django.core.mail import EmailMultiAlternatives, BadHeaderError
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import datetime
from .models import ContactMessage, ContactInfo
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_contact_emails_task(contact_message_id, request_build_absolute_uri):
    """
    Background task to send both admin notification and user confirmation emails
    for a new contact message.
    """
    try:
        contact_message = ContactMessage.objects.get(id=contact_message_id)
        contact_info = ContactInfo.get_active()
        admin_email = getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)
        
        # 1. Send Admin Notification
        try:
            admin_context = {
                'name': contact_message.name,
                'email': contact_message.email,
                'subject': contact_message.subject,
                'message': contact_message.message,
                'submitted_at': contact_message.created_at,
                'ip_address': contact_message.ip_address,
                'site_name': contact_info.company_name if contact_info else 'Nestova',
                'admin_url': request_build_absolute_uri,
                'current_year': datetime.now().year,
            }
            html_message = render_to_string('emails/contact_admin_notification.html', admin_context)
            plain_message = strip_tags(html_message)
            
            msg = EmailMultiAlternatives(
                subject=f"New Contact Message: {contact_message.subject}",
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin_email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=True)
        except Exception as e:
            logger.error(f"Error sending admin notification email via Celery: {e}")

        # 2. Send User Confirmation
        try:
            user_context = {
                'name': contact_message.name,
                'email': contact_message.email,
                'subject': contact_message.subject,
                'message': contact_message.message,
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
            
            html_message = render_to_string('emails/contact_user_confirmation.html', user_context)
            plain_message = strip_tags(html_message)
            
            msg = EmailMultiAlternatives(
                subject="Thank you for contacting us",
                body=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[contact_message.email]
            )
            msg.attach_alternative(html_message, "text/html")
            msg.send(fail_silently=True)
        except Exception as e:
            logger.error(f"Error sending user confirmation email via Celery: {e}")
            
    except ContactMessage.DoesNotExist:
        logger.error(f"ContactMessage with ID {contact_message_id} does not exist.")


@shared_task
def send_newsletter_welcome_task(email, site_url, unsubscribe_url):
    """
    Background task to send newsletter welcome email.
    """
    try:
        contact_info = ContactInfo.get_active()
        
        email_context = {
            'site_name': contact_info.company_name if contact_info else 'Nestova',
            'site_url': site_url,
            'unsubscribe_url': unsubscribe_url,
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
        
        html_message = render_to_string('emails/newsletter_welcome.html', email_context)
        plain_message = strip_tags(html_message)
        
        msg = EmailMultiAlternatives(
            subject="Welcome to our Newsletter",
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Error sending newsletter welcome email via Celery: {e}")
