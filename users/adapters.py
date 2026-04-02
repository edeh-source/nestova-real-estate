# users/adapters.py
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Auto-connect social accounts to existing users with matching email.
        This prevents the "account already exists" error and automatically
        connects Google/Facebook accounts to existing users.
        """
        # If this social account is already connected, do nothing
        if sociallogin.is_existing:
            return
        
        # Try to get the email from the social account
        email = None
        if sociallogin.account.provider == 'google':
            email = sociallogin.account.extra_data.get('email')
        elif sociallogin.account.provider == 'facebook':
            email = sociallogin.account.extra_data.get('email')
        
        if not email:
            return
        
        # Check if a user with this email already exists
        try:
            user = User.objects.get(email=email)
            # Connect this social account to the existing user
            sociallogin.connect(request, user)
        except User.DoesNotExist:
            # No existing user, will create a new one
            # Set phone_number to None for social logins
            if hasattr(sociallogin.user, 'phone_number'):
                sociallogin.user.phone_number = None
    
    def save_user(self, request, sociallogin, form=None):
        """
        Saves a newly created social login user.
        """
        user = super().save_user(request, sociallogin, form)
        # Ensure phone_number is None for social signups
        if user.phone_number == '':
            user.phone_number = None
            user.save()
        return user