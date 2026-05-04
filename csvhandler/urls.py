# csvhandler/urls.py
from django.urls import path
from . import views

app_name = 'csvhandler'

urlpatterns = [
    # Export options page
    path('export/', views.ExportOptionsView.as_view(), name='export_options'),
    
    # Model exports
    path('export/transactions/', views.TransactionExportView.as_view(), name='export_transactions_csv'),
    path('export/goals/', views.GoalExportView.as_view(), name='export_goals_csv'),
    path('export/categories/', views.CategoryExportView.as_view(), name='export_categories_csv'),

    # Import URLs - Django only, no JavaScript needed
    path('import/', views.CSVUploadView.as_view(), name='upload'),
    path('import/<str:model_type>/', views.CSVUploadView.as_view(), name='upload_with_model'),
]