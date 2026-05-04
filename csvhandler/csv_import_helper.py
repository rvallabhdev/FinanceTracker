# csvhandler/csv_import_helper.py
import pandas as pd
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from finance.models import Transaction, Goal, Category
import logging
import os

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
        """Import data from CSV with comprehensive error handling"""
        try:
            # Check if file object exists
            if not self.csv_file_obj:
                raise ValueError("No CSV file object provided")
            
            # Check if file path exists
            if not hasattr(self.csv_file_obj, 'file'):
                raise ValueError("CSV file object has no file attribute")
            
            # Check if file exists on disk
            file_path = self.csv_file_obj.file.path
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"CSV file not found at: {file_path}")
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError("CSV file is empty (0 bytes)")
            
            # Read CSV file with error handling
            skip_rows = 1 if self.skip_header else 0
            try:
                df = pd.read_csv(file_path, skiprows=skip_rows, header=None, encoding='utf-8')
            except UnicodeDecodeError:
                # Try different encoding
                try:
                    df = pd.read_csv(file_path, skiprows=skip_rows, header=None, encoding='latin1')
                except Exception as e:
                    raise ValueError(f"Failed to read CSV file. Please ensure it's a valid CSV file. Error: {str(e)}")
            except Exception as e:
                raise ValueError(f"Failed to read CSV file: {str(e)}")
            
            # Check if dataframe is empty
            if df.empty:
                raise ValueError("CSV file has no data rows after skipping header")
            
            # Validate number of columns based on model
            expected_columns = len(self.MODEL_FIELDS.get(self.model_name, []))
            if len(df.columns) < expected_columns:
                raise ValueError(
                    f"CSV file has {len(df.columns)} columns but {self.model_name} requires at least {expected_columns} columns. "
                    f"Expected order: {', '.join(self.MODEL_FIELDS.get(self.model_name, []))}"
                )
            
            # Process each row
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        self._import_row(row, index)
                    except Exception as e:
                        self.error_count += 1
                        error_msg = f"Row {index + 1 + skip_rows}: {str(e)}"
                        self.errors.append(error_msg)
                        logger.warning(error_msg)
                        
                        # Stop if too many errors
                        if self.error_count > 100:
                            raise ValueError("Too many errors (over 100 rows). Import stopped.")
            
            # Clean up file after successful import
            try:
                self.csv_file_obj.file.delete()
                self.csv_file_obj.delete()
            except Exception as e:
                logger.warning(f"Failed to delete CSV file after import: {str(e)}")
            
            return {
                'success': self.success_count,
                'errors': self.error_count,
                'error_details': self.errors[:10]  # Return first 10 errors
            }
            
        except FileNotFoundError as e:
            logger.error(f"File not found error: {str(e)}")
            # Clean up orphaned database record
            try:
                self.csv_file_obj.delete()
            except:
                pass
            raise ValueError(f"CSV file is missing. Please upload the file again.")
            
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file is empty")
            
        except Exception as e:
            logger.exception("Error importing CSV")
            # Clean up on fatal error
            try:
                self.csv_file_obj.file.delete()
                self.csv_file_obj.delete()
            except:
                pass
            raise ValueError(f"Import failed: {str(e)}")
    
    def _import_row(self, row, index):
        """Import a single row"""
        
        if self.model_name == 'Transaction':
            self._import_transaction(row, index)
        elif self.model_name == 'Goal':
            self._import_goal(row, index)
        elif self.model_name == 'Category':
            self._import_category(row, index)
        else:
            raise ValueError(f"Unknown model name: {self.model_name}")
    
    def _import_transaction(self, row, index):
        """Import transaction from row with validation"""
        # Expected order: title, amount, transaction_type, date, category
        expected_columns = 5
        
        # Check for empty row
        if len(row) < expected_columns:
            raise ValueError(f"Expected {expected_columns} columns, got {len(row)}. Expected: Title, Amount, Type, Date, Category")
        
        # Extract and clean data
        try:
            title = str(row[0]).strip() if pd.notna(row[0]) else ""
            amount_value = row[1] if len(row) > 1 else None
            transaction_type = str(row[2]).strip().capitalize() if len(row) > 2 and pd.notna(row[2]) else ""
            date_value = row[3] if len(row) > 3 else None
            category_name = str(row[4]).strip() if len(row) > 4 and pd.notna(row[4]) else None
            
            # Validate required fields
            if not title:
                raise ValueError("Title is required")
            
            if len(title) > 255:
                title = title[:255]
                logger.warning(f"Title truncated to 255 characters: {title}")
            
            # Parse amount
            if pd.isna(amount_value):
                raise ValueError("Amount is required")
            amount = self._parse_amount(amount_value)
            if amount <= 0:
                raise ValueError(f"Amount must be greater than 0, got {amount}")
            
            # Validate transaction type
            if not transaction_type:
                raise ValueError("Transaction type is required (Income or Expense)")
            if transaction_type not in ['Income', 'Expense']:
                raise ValueError(f"Transaction type must be 'Income' or 'Expense', got '{transaction_type}'")
            
            # Parse date
            if pd.isna(date_value):
                raise ValueError("Date is required")
            date = self._parse_date(date_value)
            if not date:
                raise ValueError(f"Invalid date format: {date_value}")
            
            # Get or create category
            category = None
            if category_name:
                try:
                    category, created = Category.objects.get_or_create(
                        user=self.user,
                        name=category_name,
                        category_type=transaction_type,
                        defaults={'is_default': False}
                    )
                    if created:
                        logger.info(f"Created new category: {category_name}")
                except Exception as e:
                    raise ValueError(f"Failed to create/fetch category '{category_name}': {str(e)}")
            
            # Create transaction
            Transaction.objects.create(
                user=self.user,
                title=title,
                amount=amount,
                transaction_type=transaction_type,
                date=date,
                category=category
            )
            
            self.success_count += 1
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}")
    
    def _import_goal(self, row, index):
        """Import goal from row with validation"""
        expected_columns = 3
        
        if len(row) < expected_columns:
            raise ValueError(f"Expected {expected_columns} columns, got {len(row)}. Expected: Name, Target Amount, Deadline")
        
        try:
            name = str(row[0]).strip() if pd.notna(row[0]) else ""
            amount_value = row[1] if len(row) > 1 else None
            date_value = row[2] if len(row) > 2 else None
            
            # Validate required fields
            if not name:
                raise ValueError("Goal name is required")
            
            # Parse target amount
            if pd.isna(amount_value):
                raise ValueError("Target amount is required")
            target_amount = self._parse_amount(amount_value)
            if target_amount <= 0:
                raise ValueError(f"Target amount must be greater than 0, got {target_amount}")
            
            # Parse deadline
            if pd.isna(date_value):
                raise ValueError("Deadline date is required")
            deadline = self._parse_date(date_value)
            if not deadline:
                raise ValueError(f"Invalid deadline date format: {date_value}")
            
            # Check if deadline is in the future
            if deadline.date() < datetime.now().date():
                logger.warning(f"Goal deadline '{deadline.date()}' is in the past for goal: {name}")
            
            # Create goal
            Goal.objects.create(
                user=self.user,
                name=name,
                target_amount=target_amount,
                deadline=deadline
            )
            
            self.success_count += 1
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}")
    
    def _import_category(self, row, index):
        """Import category from row with validation"""
        expected_columns = 2
        
        if len(row) < expected_columns:
            raise ValueError(f"Expected at least {expected_columns} columns, got {len(row)}. Expected: Name, Type")
        
        try:
            name = str(row[0]).strip() if pd.notna(row[0]) else ""
            category_type = str(row[1]).strip().capitalize() if len(row) > 1 and pd.notna(row[1]) else ""
            is_default = False
            
            # Parse is_default if provided
            if len(row) > 2 and pd.notna(row[2]):
                default_value = str(row[2]).strip().lower()
                is_default = default_value in ['true', '1', 'yes', 'on']
            
            # Validate required fields
            if not name:
                raise ValueError("Category name is required")
            
            if not category_type:
                raise ValueError("Category type is required (Income or Expense)")
            if category_type not in ['Income', 'Expense']:
                raise ValueError(f"Category type must be 'Income' or 'Expense', got '{category_type}'")
            
            # Check if category already exists for this user
            category, created = Category.objects.get_or_create(
                user=self.user,
                name=name,
                category_type=category_type,
                defaults={'is_default': is_default}
            )
            
            if not created and is_default:
                # Update existing category's is_default if requested
                if category.is_default != is_default:
                    category.is_default = is_default
                    category.save()
            
            self.success_count += 1
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}")
    
    def _parse_amount(self, value):
        """Parse amount from string with better error handling"""
        try:
            if pd.isna(value):
                raise ValueError("Amount is required")
            
            # Convert to string and clean
            amount_str = str(value).strip()
            
            # Remove currency symbols and common separators
            amount_str = amount_str.replace('$', '')
            amount_str = amount_str.replace('€', '')
            amount_str = amount_str.replace('£', '')
            amount_str = amount_str.replace(',', '')
            
            # Handle negative amounts in parentheses: (123.45) -> -123.45
            if amount_str.startswith('(') and amount_str.endswith(')'):
                amount_str = '-' + amount_str[1:-1]
            
            # Remove any remaining non-numeric characters except decimal point and minus
            import re
            amount_str = re.sub(r'[^\d.-]', '', amount_str)
            
            # Handle case with multiple minus signs
            if amount_str.count('-') > 1:
                raise ValueError(f"Invalid amount format: {value}")
            
            # Parse to Decimal
            amount = Decimal(amount_str)
            
            return amount
            
        except (ValueError, TypeError, Decimal.InvalidOperation) as e:
            raise ValueError(f"Invalid amount format: '{value}'. Error: {str(e)}")
    
    def _parse_date(self, value):
        """Parse date from various formats with better error handling"""
        try:
            if pd.isna(value):
                return None
            
            date_str = str(value).strip()
            
            # Try common date formats
            date_formats = [
                '%Y-%m-%d',      # 2024-01-15
                '%d/%m/%Y',      # 15/01/2024
                '%m/%d/%Y',      # 01/15/2024
                '%Y/%m/%d',      # 2024/01/15
                '%d-%m-%Y',      # 15-01-2024
                '%m-%d-%Y',      # 01-15-2024
                '%d.%m.%Y',      # 15.01.2024
                '%b %d, %Y',     # Jan 15, 2024
                '%B %d, %Y',     # January 15, 2024
                '%d %b %Y',      # 15 Jan 2024
                '%d %B %Y',      # 15 January 2024
            ]
            
            for date_format in date_formats:
                try:
                    parsed_date = datetime.strptime(date_str, date_format).date()
                    return parsed_date
                except ValueError:
                    continue
            
            # Try pandas to_datetime as fallback
            try:
                parsed_date = pd.to_datetime(date_str).date()
                return parsed_date
            except:
                pass
            
            raise ValueError(f"Unable to parse date: '{date_str}'. Supported formats: YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.")
            
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Date parsing error for '{value}': {str(e)}")