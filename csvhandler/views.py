from django.shortcuts import render, redirect
from finance.models import Transaction, Goal, Category
from django.apps import apps
import pandas as pd
from django.http import HttpResponse, JsonResponse
from datetime import datetime, timedelta
from django import forms
from django.db.models import F, Value
from django.db.models.functions import Coalesce
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
import logging
from .models import CSVFile
from .forms import CSVUploadForm
from .csv_import_helper import SimpleCSVImporter

logger = logging.getLogger(__name__)


# Create a form for date range selection
class DateRangeExportForm(forms.Form):
    DATE_RANGE_CHOICES = [
        ('all', 'All Time'),
        ('last_30', 'Last 30 Days'),
        ('last_month', 'Last Month'),
        ('this_month', 'This Month'),
        ('custom', 'Custom Range'),
    ]
    
    date_range_type = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        widget=forms.RadioSelect,
        initial='all'
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'})
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_range_type = cleaned_data.get('date_range_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if date_range_type == 'custom':
            if not start_date:
                self.add_error('start_date', 'Start date is required for custom range')
            if not end_date:
                self.add_error('end_date', 'End date is required for custom range')
            if start_date and end_date and start_date > end_date:
                self.add_error('end_date', 'End date must be after start date')
        
        return cleaned_data


class DateRangeHelper:
    """Helper class for date range calculations"""
    
    @staticmethod
    def get_date_range_from_type(date_range_type, start_date=None, end_date=None):
        """Helper function to get date range based on selection"""
        today = datetime.now().date()
        
        if date_range_type == 'last_30':
            start = today - timedelta(days=30)
            end = today
        elif date_range_type == 'last_month':
            first_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            last_of_last_month = today.replace(day=1) - timedelta(days=1)
            start = first_of_last_month
            end = last_of_last_month
        elif date_range_type == 'this_month':
            start = today.replace(day=1)
            if today.month == 12:
                end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        elif date_range_type == 'custom':
            start = start_date
            end = end_date
        else:  # 'all'
            start = None
            end = None
        
        return start, end


def format_column(col: str) -> str:
    """Format column name for CSV export"""
    return col.replace('_', ' ').title()


class TransactionExportView(LoginRequiredMixin, View):
    """Export transactions to CSV"""
    
    def get(self, request, *args, **kwargs):
        try:
            form = DateRangeExportForm(request.GET)
            
            if form.is_valid():
                date_range_type = form.cleaned_data['date_range_type']
                start_date = form.cleaned_data.get('start_date')
                end_date = form.cleaned_data.get('end_date')
                
                # Get date range based on selection
                start_date_obj, end_date_obj = DateRangeHelper.get_date_range_from_type(
                    date_range_type, start_date, end_date
                )
                
                # Base queryset
                transactions = Transaction.objects.filter(user=request.user)
                
                # Apply date filters
                if start_date_obj:
                    transactions = transactions.filter(date__gte=start_date_obj)
                if end_date_obj:
                    transactions = transactions.filter(date__lte=end_date_obj)
                
                # Order by date (newest first)
                transactions = transactions.order_by('-date')
                
                # Get values with category name
                transactions = transactions.select_related('category').annotate(
                    category_name=Coalesce(F('category__name'), Value('Uncategorized'))
                ).values(
                    'title', 'amount', 'transaction_type', 'date', 'category_name'
                )

                # Handle empty dataset
                if not transactions.exists():
                    return JsonResponse({
                        'message': 'No transactions found in the selected date range',
                        'status': 404
                    })

                # Create DataFrame
                df = pd.DataFrame(transactions)
                
                # Rename category_name to category
                df = df.rename(columns={'category_name': 'category'})
                
                # Format column names
                df.columns = [format_column(col) for col in df.columns]

                # Prepare response
                response = HttpResponse(content_type='text/csv')
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Create filename
                if date_range_type == 'custom' and start_date and end_date:
                    filename = f"transactions_{start_date}_to_{end_date}_{current_time}.csv"
                elif date_range_type == 'all':
                    filename = f"transactions_all_{current_time}.csv"
                else:
                    filename = f"transactions_{date_range_type}_{current_time}.csv"
                
                response['Content-Disposition'] = f'attachment; filename="{filename}"'

                # Add summary
                response.write('Transaction Report\n')
                response.write(f'Date Range Type: {date_range_type}\n')
                response.write(f'Total Records: {len(df)}\n')
                response.write('='*50 + '\n\n')
                
                # Write CSV
                df.to_csv(response, index=False)

                return response
            else:
                return render(request, 'csvhandler/export_options.html', {'form': form, 'model_name': 'Transactions'})

        except Exception as e:
            logger.exception("Error exporting transactions CSV")
            return JsonResponse({
                'message': f'Failed to export transactions: {str(e)}',
                'status': 500
            })


class GoalExportView(LoginRequiredMixin, View):
    """Export goals to CSV"""
    
    def get(self, request, *args, **kwargs):
        try:
            form = DateRangeExportForm(request.GET)
            
            if form.is_valid():
                date_range_type = form.cleaned_data['date_range_type']
                start_date = form.cleaned_data.get('start_date')
                end_date = form.cleaned_data.get('end_date')
                
                # Get date range based on selection
                start_date_obj, end_date_obj = DateRangeHelper.get_date_range_from_type(
                    date_range_type, start_date, end_date
                )
                
                # Base queryset
                goals = Goal.objects.filter(user=request.user)
                
                # Apply date filters
                if start_date_obj:
                    goals = goals.filter(deadline__gte=start_date_obj)
                if end_date_obj:
                    goals = goals.filter(deadline__lte=end_date_obj)
                
                # Order by deadline
                goals = goals.order_by('deadline')
                
                # Get values
                goals = goals.values('name', 'target_amount', 'deadline')

                # Handle empty dataset
                if not goals.exists():
                    return JsonResponse({
                        'message': 'No goals found in the selected date range',
                        'status': 404
                    })

                # Create DataFrame
                df = pd.DataFrame(goals)
                
                # Format column names
                df.columns = [format_column(col) for col in df.columns]

                # Prepare response
                response = HttpResponse(content_type='text/csv')
                current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Create filename
                if date_range_type == 'custom' and start_date and end_date:
                    filename = f"goals_{start_date}_to_{end_date}_{current_time}.csv"
                elif date_range_type == 'all':
                    filename = f"goals_all_{current_time}.csv"
                else:
                    filename = f"goals_{date_range_type}_{current_time}.csv"
                
                response['Content-Disposition'] = f'attachment; filename="{filename}"'

                # Add summary
                response.write('Goal Report\n')
                response.write(f'Date Range Type: {date_range_type}\n')
                response.write(f'Total Records: {len(df)}\n')
                response.write('='*50 + '\n\n')
                
                # Write CSV
                df.to_csv(response, index=False)

                return response
            else:
                return render(request, 'csvhandler/export_options.html', {'form': form, 'model_name': 'Goals'})

        except Exception as e:
            logger.exception("Error exporting goals CSV")
            return JsonResponse({
                'message': f'Failed to export goals: {str(e)}',
                'status': 500
            })


class CategoryExportView(LoginRequiredMixin, View):
    """Export categories to CSV - Simple and clean"""
    
    def get(self, request, *args, **kwargs):
        try:
            # Get all categories for the user
            categories = Category.objects.filter(user=request.user).values('name', 'category_type')
            
            # Handle empty dataset
            if not categories.exists():
                return JsonResponse({
                    'message': 'No categories found',
                    'status': 404
                })
            
            # Create DataFrame
            df = pd.DataFrame(categories)
            
            # Format column names
            df.columns = [format_column(col) for col in df.columns]
            
            # Prepare response
            response = HttpResponse(content_type='text/csv')
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"categories_{current_time}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Add summary
            response.write('Categories Report\n')
            response.write(f'Total Records: {len(df)}\n')
            response.write('='*50 + '\n\n')
            
            # Write CSV
            df.to_csv(response, index=False)
            
            return response
            
        except Exception as e:
            logger.exception("Error exporting categories CSV")
            return JsonResponse({
                'message': f'Failed to export categories: {str(e)}',
                'status': 500
            })


class ExportOptionsView(LoginRequiredMixin, View):
    """View to show export options with date range picker"""
    
    def get(self, request, *args, **kwargs):
        form = DateRangeExportForm()
        model_name = request.GET.get('type', 'Transactions')
        return render(request, 'csvhandler/export_options.html', {
            'form': form,
            'model_name': model_name
        })


# csvhandler/views.py - Updated CSVUploadView
class CSVUploadView(LoginRequiredMixin, View):
    """Simple CSV upload and import view"""
    
    def get(self, request, model_type=None):
        form = CSVUploadForm()
        recent_imports = CSVFile.objects.filter().order_by('-uploaded_at')[:10]
        
        return render(request, 'csvhandler/upload.html', {
            'form': form,
            'recent_imports': recent_imports,
            'selected_model': model_type
        })
    
    def post(self, request, model_type=None):
        # Get model_name from hidden field or URL
        model_name = request.POST.get('model_name') or model_type
        
        if not model_name:
            messages.error(request, "No model selected for import")
            return redirect('csvhandler:upload')
        
        form = CSVUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Save the CSV file
            csv_file = form.save()
            
            # Get import parameters
            skip_header = request.POST.get('skip_header') == 'on'
            
            # Import the data
            importer = SimpleCSVImporter(
                user=request.user,
                csv_file_obj=csv_file,
                model_name=model_name,
                skip_header=skip_header
            )
            
            try:
                result = importer.import_data()
                
                if result['errors'] == 0:
                    messages.success(
                        request,
                        f"Successfully imported {result['success']} {model_name}(s)!"
                    )
                else:
                    messages.warning(
                        request,
                        f"Imported {result['success']} {model_name}(s) with {result['errors']} errors. "
                        f"Errors: {'; '.join(result['error_details'][:3])}"
                    )
                
                # Redirect back to the same model type
                return redirect('csvhandler:upload_with_model', model_type=model_name)
                
            except Exception as e:
                messages.error(request, f"Import failed: {str(e)}")
                return redirect('csvhandler:upload_with_model', model_type=model_name)
        
        # If form is invalid
        recent_imports = CSVFile.objects.filter().order_by('-uploaded_at')[:10]
        return render(request, 'csvhandler/upload.html', {
            'form': form,
            'recent_imports': recent_imports,
            'selected_model': model_name
        })