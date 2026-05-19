from django.db import models


class CommunityEvent(models.Model):
    name       = models.CharField(max_length=200)
    image      = models.ImageField(upload_to='events/')
    image_alt  = models.CharField(max_length=200, blank=True,
                                  help_text="Alt text — defaults to event name if left blank")
    event_date = models.DateField(help_text="Displayed as 'Month YYYY'")
    is_active  = models.BooleanField(default=True)
    order      = models.PositiveSmallIntegerField(default=0,
                                                  help_text="Lower = shown first")

    class Meta:
        ordering = ['order', '-event_date']
        verbose_name        = 'Community Event'
        verbose_name_plural = 'Community Events'

    def __str__(self):
        return self.name

    def get_alt(self):
        return self.image_alt or self.name

    def formatted_date(self):
        return self.event_date.strftime('%B %Y')   # → "November 2025"