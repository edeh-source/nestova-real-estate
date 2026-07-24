from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_password_reset_email_task(user_email, user_first_name, reset_link):
    """
    Background task to send password reset email.
    """
    try:
        context = {
            'user': {'first_name': user_first_name},
            'reset_link': reset_link,
            'site_name': 'Nestova',
        }
        
        html_content = render_to_string('estate/password_reset_email.html', context)
        
        subject = 'Password Reset Request - Nestova'
        from_email = settings.DEFAULT_FROM_EMAIL
        
        msg = EmailMultiAlternatives(subject, '', from_email, [user_email])
        msg.attach_alternative(html_content, "text/html")
        
        msg.send()
    except Exception as e:
        logger.error(f"Error sending password reset email via Celery: {e}")
