# csvhandler/csv_import_helper.py
import pandas as pd
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from finance.models import Transaction, Goal, Category
import logging

logger = logging.getLogger(__name__)


class SimpleCSVImporter:
    """Simple CSV importer assuming columns match model field order"""
    
    # Define field order for each model (excluding 'user' and 'id')
    MODEL_FIELDS = {
        'Transaction': ['title', 'amount', 'transaction_type', 'date', 'category'],
        'Goal': ['name', 'target_amount', 'deadline'],
        'Category': ['name', 'category_type', 'is_default'],
    }
    
    def __init__(self, user, csv_file_obj, model_name, skip_header=True):
        self.user = user
        self.csv_file_obj = csv_file_obj
        self.model_name = model_name
        self.skip_header = skip_header
        self.success_count = 0
        self.error_count = 0
        self.errors = []
    
    def import_data(self):
        """Import data from CSV"""
        try:
            # Read CSV file
            skip_rows = 1 if self.skip_header else 0
            df = pd.read_csv(self.csv_file_obj.file.path, skiprows=skip_rows, header=None)
            
            # Process each row
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        self._import_row(row, index)
                    except Exception as e:
                        self.error_count += 1
                        self.errors.append(f"Row {index + 1 + skip_rows}: {str(e)}")
            
            return {
                'success': self.success_count,
                'errors': self.error_count,
                'error_details': self.errors[:5]
            }
            
        except Exception as e:
            logger.exception("Error importing CSV")
            raise
    
    def _import_row(self, row, index):
        """Import a single row"""
        
        if self.model_name == 'Transaction':
            self._import_transaction(row, index)
        elif self.model_name == 'Goal':
            self._import_goal(row, index)
        elif self.model_name == 'Category':
            self._import_category(row, index)
    
    def _import_transaction(self, row, index):
        """Import transaction from row"""
        # Expected order: title, amount, transaction_type, date, category
        if len(row) < 5:
            raise ValueError(f"Expected at least 5 columns, got {len(row)}")
        
        title = str(row[0]).strip()
        amount = self._parse_amount(row[1])
        transaction_type = str(row[2]).strip().capitalize()
        date = self._parse_date(row[3])
        category_name = str(row[4]).strip() if pd.notna(row[4]) else None
        
        # Validate
        if not title:
            raise ValueError("Title is required")
        if transaction_type not in ['Income', 'Expense']:
            raise ValueError(f"Transaction type must be Income/Expense, got {transaction_type}")
        
        # Get or create category
        category = None
        if category_name:
            category, _ = Category.objects.get_or_create(
                user=self.user,
                name=category_name,
                category_type=transaction_type,
                defaults={'is_default': False}
            )
        
        # Create transaction
        Transaction.objects.create(
            user=self.user,
            title=title[:255],
            amount=amount,
            transaction_type=transaction_type,
            date=date,
            category=category
        )
        
        self.success_count += 1
    
    def _import_goal(self, row, index):
        """Import goal from row"""
        # Expected order: name, target_amount, deadline
        if len(row) < 3:
            raise ValueError(f"Expected at least 3 columns, got {len(row)}")
        
        name = str(row[0]).strip()
        target_amount = self._parse_amount(row[1])
        deadline = self._parse_date(row[2])
        
        if not name:
            raise ValueError("Name is required")
        
        Goal.objects.create(
            user=self.user,
            name=name,
            target_amount=target_amount,
            deadline=deadline
        )
        
        self.success_count += 1
    
    def _import_category(self, row, index):
        """Import category from row"""
        # Expected order: name, category_type, is_default
        if len(row) < 2:
            raise ValueError(f"Expected at least 2 columns, got {len(row)}")
        
        name = str(row[0]).strip()
        category_type = str(row[1]).strip().capitalize()
        is_default = bool(row[2]) if len(row) > 2 and pd.notna(row[2]) else False
        
        if not name:
            raise ValueError("Name is required")
        if category_type not in ['Income', 'Expense']:
            raise ValueError(f"Category type must be Income/Expense, got {category_type}")
        
        # Check if category already exists for this user
        category, created = Category.objects.get_or_create(
            user=self.user,
            name=name,
            category_type=category_type,
            defaults={'is_default': is_default}
        )
        
        self.success_count += 1
    
    def _parse_amount(self, value):
        """Parse amount from string"""
        if pd.isna(value):
            raise ValueError("Amount is required")
        
        # Remove $, commas, and convert to Decimal
        cleaned = str(value).replace('$', '').replace(',', '').strip()
        return Decimal(cleaned)
    
    def _parse_date(self, value):
        """Parse date from various formats"""
        if pd.isna(value):
            raise ValueError("Date is required")
        
        date_str = str(value)
        # Try common date formats
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y']:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # Try pandas as fallback
        try:
            return pd.to_datetime(date_str).date()
        except:
            raise ValueError(f"Unable to parse date: {date_str}")