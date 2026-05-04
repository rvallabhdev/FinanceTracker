# csvhandler/utils.py
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db.models import QuerySet
import pandas as pd
import logging

logger = logging.getLogger(__name__)


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
        end = today
    elif date_range_type == 'custom':
        start = start_date
        end = end_date
    else:  # 'all'
        start = None
        end = None
    
    return start, end


def format_column_name(col: str) -> str:
    """Format column name for CSV export"""
    return col.replace('_', ' ').title()


def export_to_csv(queryset: QuerySet, fields: list = None, filename: str = None, 
                  field_mapping: dict = None, add_metadata: bool = True) -> HttpResponse:
    """
    Generic CSV export function for any Django queryset
    
    Args:
        queryset: Django QuerySet to export
        fields: List of field names to include (None for all fields)
        filename: Custom filename (auto-generated if None)
        field_mapping: Dictionary to rename columns {old_name: new_name}
        add_metadata: Whether to add metadata header
    
    Returns:
        HttpResponse with CSV file
    """
    try:
        # Convert queryset to DataFrame
        if fields:
            data = queryset.values(*fields)
        else:
            data = queryset.values()
        
        if not data:
            raise ValueError("No data to export")
        
        df = pd.DataFrame(list(data))
        
        # Apply field mapping if provided
        if field_mapping:
            df = df.rename(columns=field_mapping)
        else:
            # Format column names
            df.columns = [format_column_name(col) for col in df.columns]
        
        # Prepare response
        response = HttpResponse(content_type='text/csv')
        
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = queryset.model.__name__.lower()
            filename = f"{model_name}_export_{timestamp}.csv"
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Add metadata if requested
        if add_metadata:
            response.write(f'# Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
            response.write(f'# Total Records: {len(df)}\n')
            response.write(f'# Model: {queryset.model.__name__}\n')
            response.write('# ' + '='*60 + '\n\n')
        
        # Write CSV
        df.to_csv(response, index=False)
        
        return response
        
    except Exception as e:
        logger.exception(f"Error exporting to CSV: {str(e)}")
        raise


class CSVExporter:
    """Class-based exporter for complex exports with custom filtering"""
    
    def __init__(self, model, fields=None, field_mapping=None, date_field='date'):
        self.model = model
        self.fields = fields or [f.name for f in model._meta.fields if f.name not in ['id', 'user']]
        self.field_mapping = field_mapping or {}
        self.date_field = date_field
        
    def get_queryset(self, user=None, date_range_type='all', start_date=None, end_date=None):
        """Get filtered queryset based on parameters"""
        queryset = self.model.objects.all()
        
        # Filter by user if model has user field
        if user and hasattr(self.model, 'user'):
            queryset = queryset.filter(user=user)
        
        # Apply date filters
        if self.date_field and hasattr(self.model, self.date_field):
            start_date_obj, end_date_obj = get_date_range_from_type(
                date_range_type, start_date, end_date
            )
            
            filter_kwargs = {}
            if start_date_obj:
                filter_kwargs[f'{self.date_field}__gte'] = start_date_obj
            if end_date_obj:
                filter_kwargs[f'{self.date_field}__lte'] = end_date_obj
            
            if filter_kwargs:
                queryset = queryset.filter(**filter_kwargs)
        
        return queryset.order_by(f'-{self.date_field}' if self.date_field else '-id')
    
    def get_filename(self, date_range_type='all', start_date=None, end_date=None):
        """Generate descriptive filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = self.model.__name__.lower()
        
        if date_range_type == 'custom' and start_date and end_date:
            return f"{model_name}_{start_date}_to_{end_date}_{timestamp}.csv"
        elif date_range_type != 'all':
            return f"{model_name}_{date_range_type}_{timestamp}.csv"
        else:
            return f"{model_name}_all_{timestamp}.csv"
    
    def export(self, user=None, date_range_type='all', start_date=None, end_date=None, 
               filename=None, add_metadata=True):
        """Main export method"""
        queryset = self.get_queryset(user, date_range_type, start_date, end_date)
        
        if not queryset.exists():
            raise ValueError("No data found for the selected criteria")
        
        if not filename:
            filename = self.get_filename(date_range_type, start_date, end_date)
        
        return export_to_csv(queryset, self.fields, filename, self.field_mapping, add_metadata)