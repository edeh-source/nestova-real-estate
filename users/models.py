from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import uuid
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.conf import settings



class UserManager(BaseUserManager):
    """
    A method to override the user 

    Args:
        BaseUserManager (_type_): _description_

    Returns:
        _type_: _description_
    """
    
    def create_user(self, username, email, phone_number, password, **kwargs):
        """
        """
        if not username:
            raise ValidationError("Username Field Must Be Provided")
        
        if not email:
            raise ValidationError("Email Field Must Be Provided")
        
        if not phone_number:
            raise ValidationError("Phone Number Field Must Be Provided")
        
        if not password:
            raise ValidationError("Password Field Must Be Provided")
        
        user = self.model(username=username, email=self.normalize_email(email), phone_number=phone_number, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    
    
    def create_superuser(self, username, email, password, **kwargs):
        """
        """
        if not username:
            raise ValidationError("Username Field Must Be Provided")
        
        if not email:
            raise ValidationError("Email Field Must Be Provided")
        
        if not password:
            raise ValidationError("Password Field Must Be Provided")
        
        user = self.model(username=username, email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class User(PermissionsMixin, AbstractBaseUser):
    """_summary_

    Args:
        PermissionsMixin (_type_): _description_
        AbstractBaseUser (_type_): _description_
    """
    ACCOUNT_TYPE_CHOICES = [
        ('user', 'Normal User'),
        ('agent', 'Agent'),
        ('company', 'Company'),
    ]
    
    id = models.UUIDField(unique=True, primary_key=True, editable=False, default=uuid.uuid4)
    username = models.CharField(max_length=256, db_index=True, unique=True)
    first_name = models.CharField(max_length=256, blank=True, null=True)
    last_name = models.CharField(max_length=256, db_index=True, blank=True, null=True)
    phone_number = PhoneNumberField(unique=True, db_index=True, blank=True, null=True)
    email = models.EmailField(unique=True, max_length=200)
    image = models.ImageField(upload_to="users_image", blank=True, null=True)
    
    # Account type
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default='user')
    
    # Status flags
    is_active = models.BooleanField(default=True)
    is_agent = models.BooleanField(default=False)
    is_company = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Verification fields for normal users
    id_verified = models.BooleanField(default=False, help_text="User has verified their ID")
    id_type = models.CharField(max_length=20, blank=True, null=True, help_text="nin, vnin, or bvn")
    id_number = models.CharField(max_length=50, blank=True, null=True, help_text="ID number used for verification")
    id_verification_date = models.DateTimeField(null=True, blank=True)
    verification_data = models.JSONField(default=dict, blank=True, help_text="API verification response data")
    can_post_properties = models.BooleanField(default=False, help_text="User can post properties after verification")
    
    created = models.DateTimeField(auto_now=True)
    updated = models.DateTimeField(auto_now=True)

    
    
    def __str__(self):
        return self.username
    
    
    
    
    def get_users_image(self):
        """
        """    
        if self.image:
            return self.image.url
        else:
            return settings.MEDIA_URL + "user-blank.webp"
    
    def get_full_name(self):
        """Return the user's full name or username as fallback"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username
    
    
    objects = UserManager()
    
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username',]

