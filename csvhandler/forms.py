# csvhandler/forms.py
from django import forms
from datetime import datetime


class DateRangeExportForm(forms.Form):
    """Generic form for date range based exports"""
    
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


class GenericExportForm(forms.Form):
    """Generic form for any model export with field selection"""
    
    def __init__(self, *args, **kwargs):
        model_fields = kwargs.pop('model_fields', [])
        super().__init__(*args, **kwargs)
        
        # Add field selection checkboxes
        self.fields['fields'] = forms.MultipleChoiceField(
            choices=[(field, field.replace('_', ' ').title()) for field in model_fields],
            widget=forms.CheckboxSelectMultiple,
            required=True,
            initial=model_fields
        )
        
        # Add format choice
        self.fields['format'] = forms.ChoiceField(
            choices=[('csv', 'CSV'), ('excel', 'Excel (coming soon)')],
            widget=forms.RadioSelect,
            initial='csv'
        )


# CSV Import Form - Regular Form (not ModelForm)
class CSVUploadForm(forms.Form):
    """Form for uploading CSV files - no database storage"""
    
    # ADDED: file field (was missing)
    file = forms.FileField(
        label="CSV File",
        required=True,
        widget=forms.FileInput(attrs={
            'class': 'w-full',
            'accept': '.csv',
            'id': 'csvFileInput'
        })
    )
    
    skip_header = forms.BooleanField(
        required=False,
        initial=True,
        label="Skip header row (first row contains column names)",
        widget=forms.CheckboxInput(attrs={'class': 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'})
    )
    
    def clean_file(self):
        file = self.cleaned_data.get('file')  # CHANGED: use .get() to avoid KeyError
        
        if not file:  # ADDED: check if file exists
            raise forms.ValidationError('Please select a CSV file')
        
        if not file.name.endswith('.csv'):
            raise forms.ValidationError('Only CSV files are allowed')
        
        # Check file size (max 5MB)
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File too large (max 5MB)')
        
        return file