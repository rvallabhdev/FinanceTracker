from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .utils import create_default_categories
from .models import Category


@receiver(post_save, sender=User)
def create_user_categories(sender, instance, created, **kwargs):
    if created:
        print("SIGNAL FIRED")  # 👈 DEBUG LINE
        create_default_categories(instance)