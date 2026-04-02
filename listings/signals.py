from django.db.models.signals import post_delete
from django.dispatch import receiver
from property.models import Property


@receiver(post_delete, sender=Property)
def release_slot_on_property_delete(sender, instance, **kwargs):
    """
    Automatically release a slot when a property is deleted.
    """
    from listings.models import UserSubscription
    
    # Get user's subscription
    try:
        sub = UserSubscription.objects.get(user=instance.listed_by)
        sub.release_slot()
    except UserSubscription.DoesNotExist:
        pass
