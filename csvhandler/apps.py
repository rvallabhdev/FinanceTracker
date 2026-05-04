# csvhandler/apps.py
from django.apps import AppConfig

class CsvhandlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'csvhandler'
    verbose_name = 'CSV Handler'