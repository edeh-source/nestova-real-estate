from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from property.models import Property


@receiver(post_delete, sender=Property)
def on_property_deleted(sender, instance, **kwargs):
    """
    When a property is deleted:
    - Slot count adjusts automatically (active_listing_count is a live DB query,
      so no stored counter needs decrementing).
    - A notification is sent so the agent knows a slot has freed up.
    """
    from listings.models import UserSubscription, Notification

    try:
        sub = UserSubscription.objects.get(user=instance.listed_by)
    except UserSubscription.DoesNotExist:
        return

    Notification.objects.create(
        user=instance.listed_by,
        title="Listing removed",
        message=(
            f"Your property '{instance.title}' has been deleted. "
            f"You now have {sub.remaining_listings} of {sub.listing_limit} "
            f"listing slots available."
        ),
        link='/listings/dashboard/',
    )


@receiver(post_save, sender=Property)
def on_property_saved(sender, instance, created, **kwargs):
    """
    When a new property is posted:
    - Notify the user of remaining slots.
    - Warn at 80 % usage so agents know to upgrade before hitting the cap.
    """
    if not created:
        return

    from listings.models import UserSubscription, Notification

    try:
        sub = UserSubscription.objects.get(user=instance.listed_by)
    except UserSubscription.DoesNotExist:
        return

    usage_pct = sub.slots_usage_percentage

    if sub.remaining_listings == 0:
        Notification.objects.create(
            user=instance.listed_by,
            title="Listing limit reached",
            message=(
                f"You've used all {sub.listing_limit} listing slots on your current plan. "
                "Upgrade to post more properties."
            ),
            link='/listings/pricing/',
        )
    elif usage_pct >= 80:
        Notification.objects.create(
            user=instance.listed_by,
            title="Approaching listing limit",
            message=(
                f"You've used {sub.active_listing_count} of {sub.listing_limit} listing "
                f"slots ({usage_pct}%). Consider upgrading your plan soon."
            ),
            link='/listings/pricing/',
        )