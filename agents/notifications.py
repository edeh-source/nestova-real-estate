"""
Notification system for verification status updates.
Sends email notifications when verification status changes.
"""

from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def notify_verification_approved(user, user_type='agent'):
    """
    Send email notification when verification is approved.
    
    Args:
        user: User object
        user_type: 'agent', 'company', or 'individual'
    """
    try:
        subject = f"✅ Your {user_type.title()} Account is Verified!"
        
        message = f"""
Dear {user.first_name or user.username},

Congratulations! Your {user_type} account has been successfully verified.

You can now:
- Post properties on our platform
- Access all premium features
- Start earning commissions (for agents)

Login to your dashboard: {settings.SITE_URL}/shop/profile

If you have any questions, please contact our support team.

Best regards,
The Nestova Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Verification approved email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification approved email to {user.email}: {str(e)}")
        return False


def notify_verification_rejected(user, reason, user_type='agent'):
    """
    Send email notification when verification is rejected.
    
    Args:
        user: User object
        reason: Rejection reason
        user_type: 'agent', 'company', or 'individual'
    """
    try:
        subject = f"❌ Your {user_type.title()} Verification Was Not Approved"
        
        message = f"""
Dear {user.first_name or user.username},

Unfortunately, your {user_type} verification could not be approved at this time.

Reason: {reason}

What you can do:
1. Review the information you provided
2. Ensure all documents are clear and valid
3. Make sure your information matches your ID documents exactly
4. Resubmit your verification

If you believe this is an error or need assistance, please contact our support team.

Resubmit verification: {settings.SITE_URL}/agents/verification-dashboard

Best regards,
The Nestova Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Verification rejected email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification rejected email to {user.email}: {str(e)}")
        return False


def notify_verification_in_review(user, user_type='agent'):
    """
    Send email notification when verification is under manual review.
    
    Args:
        user: User object
        user_type: 'agent', 'company', or 'individual'
    """
    try:
        subject = f"⏳ Your {user_type.title()} Verification is Under Review"
        
        message = f"""
Dear {user.first_name or user.username},

Thank you for submitting your {user_type} verification documents.

Your verification is currently under review by our team. This process typically takes 24-48 hours.

We will notify you via email once the review is complete.

You can check your verification status at any time: {settings.SITE_URL}/agents/verification-dashboard

Thank you for your patience!

Best regards,
The Nestova Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Verification in review email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send verification in review email to {user.email}: {str(e)}")
        return False
