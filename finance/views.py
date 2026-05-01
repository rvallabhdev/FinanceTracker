from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.views import View
from finance.forms import GoalForm, RegisterForm, TransactionForm
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Transaction, Goal
from django.db.models import Sum
from django.contrib import messages

# ============================================
# USER REGISTRATION VIEW
# ============================================
class RegisterView(View):
    """
    Handles user registration.
    
    WORKFLOW:
    1. GET request: Display empty registration form
    2. POST request: Validate form data, create user, log them in automatically
    3. After successful registration, redirect to dashboard
    
    LOGIC:
    - Uses custom RegisterForm (extends Django's UserCreationForm)
    - Auto-login after registration (no need for separate login step)
    - Redirects to dashboard which requires login (LoginRequiredMixin will protect it)
    """
    def get(self, request, *args, **kwargs):
        """Display empty registration form"""
        form = RegisterForm()
        return render(request, 'finance/register.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        """Process registration form submission"""
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Create new user
            login(request, user)  # Auto-login the user
            return redirect('dashboard')  # Redirect to dashboard


# ============================================
# MAIN DASHBOARD VIEW
# ============================================
class DashboardView(LoginRequiredMixin, View):
    """
    Main dashboard showing financial overview.
    Requires authentication (LoginRequiredMixin)
    
    WORKFLOW:
    1. Fetch user's transactions and goals
    2. Calculate total income, expenses, and net savings
    3. Allocate savings to goals in deadline order
    4. Calculate progress percentage for each goal
    5. Pass all data to dashboard template
    
    LOGIC FOR GOAL PROGRESS CALCULATION:
    - Goals are processed in deadline order (earliest deadline first)
    - remaining_savings starts as net_savings (income - expense)
    - For each goal:
        * If savings >= target: goal gets 100% progress, subtract target from savings
        * If savings > 0 but less than target: goal gets partial percentage, savings becomes 0
        * If savings = 0: goal gets 0% progress
    - This shows which goals can be achieved with current savings
    """
    def get(self, request, *args, **kwargs):
        # Fetch user data
        transactions = Transaction.objects.filter(user=request.user).order_by('-date')
        goals = Goal.objects.filter(user=request.user).order_by('deadline')
        
        # Calculate financial totals
        total_income = Transaction.objects.filter(
            user=request.user, 
            transaction_type='Income'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_expense = Transaction.objects.filter(
            user=request.user, 
            transaction_type='Expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        net_savings = total_income - total_expense
        
        # Goal progress allocation logic
        goal_progress = []
        remaining_savings = net_savings  # Track savings pool
        
        for goal in goals:
            if remaining_savings >= goal.target_amount:
                # Scenario 1: Enough savings to fully fund this goal
                progress = 100
                goal_progress.append({
                    'goal': goal,
                    'progress': progress,
                })
                remaining_savings -= goal.target_amount  # Deduct used savings
                
            elif remaining_savings > 0:
                # Scenario 2: Partial funding available
                progress = (remaining_savings / goal.target_amount) * 100
                goal_progress.append({
                    'goal': goal,
                    'progress': progress,
                })
                remaining_savings = 0  # All savings exhausted
                
            else:
                # Scenario 3: No savings remaining
                progress = 0
                goal_progress.append({
                    'goal': goal,
                    'progress': progress,
                })
        
        context = {
            'transactions': transactions,
            'goals': goals,
            'goal_progress': goal_progress,
            'total_income': total_income,
            'total_expense': total_expense,
            'net_savings': net_savings,
        }   
        return render(request, 'finance/dashboard.html', context)


# ============================================
# TRANSACTION CRUD OPERATIONS
# ============================================
class TransactionCreateView(LoginRequiredMixin, View):
    """
    Create new transaction (Income or Expense)
    
    WORKFLOW:
    1. GET: Display empty form
    2. POST: Validate form, assign user, save to database
    3. Show success message and redirect to transaction list
    
    LOGIC:
    - Uses TransactionForm (ModelForm for Transaction model)
    - commit=False to add user before saving
    - Uses Django messages framework for user feedback
    """
    def get(self, request, *args, **kwargs):
        form = TransactionForm()
        return render(request, 'finance/transaction_form.html', {'form': form, 'is_edit': False})
    
    def post(self, request, *args, **kwargs):
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)  # Don't save to DB yet
            transaction.user = request.user  # Assign logged-in user
            transaction.save()  # Now save to DB
            messages.success(request, f'Transaction "{transaction.title}" added successfully!')
            return redirect('transaction_list')
        return render(request, 'finance/transaction_form.html', {'form': form, 'is_edit': False})


class TransactionEditView(LoginRequiredMixin, View):
    """
    Edit existing transaction
    
    WORKFLOW:
    1. GET: Fetch transaction by ID, verify ownership, populate form with existing data
    2. POST: Validate updated data, save to database
    3. Show success message and redirect to transaction list
    
    SECURITY:
    - get_object_or_404 ensures user can only access their own transactions
    - user=request.user prevents accessing other users' data
    """
    def get(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        form = TransactionForm(instance=transaction)  # Pre-fill form with existing data
        return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction, 'is_edit': True})
    
    def post(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        form = TransactionForm(request.POST, instance=transaction)  # Update existing instance
        if form.is_valid():
            form.save()  # Updates the existing record
            messages.success(request, f'Transaction "{transaction.title}" updated successfully!')
            return redirect('transaction_list')
        return render(request, 'finance/transaction_form.html', {'form': form, 'transaction': transaction, 'is_edit': True})


class TransactionDeleteView(LoginRequiredMixin, View):
    """
    Delete transaction
    
    WORKFLOW:
    1. POST: Get transaction by ID, verify ownership, delete from database
    2. Show success message, redirect to transaction list
    
    NOTE: Uses POST method (not GET) for security - prevents accidental deletions
    """
    def post(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        title = transaction.title  # Store title before deletion (for success message)
        transaction.delete()
        messages.success(request, f'Transaction "{title}" deleted successfully!')
        return redirect('transaction_list')


class TransactionListView(LoginRequiredMixin, View):
    """
    Display all user transactions with summary
    
    WORKFLOW:
    1. Fetch all user transactions ordered by date (newest first)
    2. Calculate total income and expense for summary cards
    3. Pass to template for display
    
    LOGIC:
    - Uses aggregate() with Sum for efficient database calculation
    - or 0 handles case when no transactions exist
    - Transaction amounts show with + or - signs in template
    """
    def get(self, request, *args, **kwargs): 
        transactions = Transaction.objects.filter(user=request.user).order_by('-date')
        
        # Calculate summary statistics
        total_income = Transaction.objects.filter(
            user=request.user, 
            transaction_type='Income'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        total_expense = Transaction.objects.filter(
            user=request.user, 
            transaction_type='Expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        context = {
            'transactions': transactions,
            'total_income': total_income,
            'total_expense': total_expense,
        }
        
        return render(request, 'finance/transaction_list.html', context)


# ============================================
# GOAL CRUD OPERATIONS
# ============================================
class GoalCreateView(LoginRequiredMixin, View):
    """
    Create new financial goal
    
    WORKFLOW:
    1. GET: Display empty form
    2. POST: Validate form, assign user, save to database
    3. Show success message and redirect to dashboard
    
    NOTE: Goal model tracks target_amount only (not current_amount)
    Progress is calculated in DashboardView based on savings allocation
    """
    def get(self, request, *args, **kwargs):
        form = GoalForm()
        return render(request, 'finance/goal_form.html', {'form': form})
    
    def post(self, request, *args, **kwargs):
        form = GoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.name}" created successfully!')
            return redirect('dashboard')  # Redirect to dashboard to see goal progress
        return render(request, 'finance/goal_form.html', {'form': form})


class GoalEditView(LoginRequiredMixin, View):
    """
    Edit existing goal
    
    WORKFLOW:
    1. GET: Fetch goal by ID, verify ownership, populate form with existing data
    2. POST: Validate updated data, save to database
    3. Show success message and redirect to dashboard
    
    SECURITY: get_object_or_404 filters by user=request.user
    """
    def get(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        form = GoalForm(instance=goal)
        return render(request, 'finance/goal_form.html', {'form': form, 'goal': goal})
    
    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, f'Goal "{goal.name}" updated successfully!')
            return redirect('dashboard')
        return render(request, 'finance/goal_form.html', {'form': form, 'goal': goal})


class GoalDeleteView(LoginRequiredMixin, View):
    """
    Delete goal
    
    WORKFLOW:
    1. POST: Get goal by ID, verify ownership, delete from database
    2. Show success message, redirect to dashboard
    
    NOTE: Uses POST method for security (CSRF protection)
    """
    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        name = goal.name
        goal.delete()
        messages.success(request, f'Goal "{name}" deleted successfully!')
        return redirect('dashboard')  # Return to dashboard


class GoalListView(LoginRequiredMixin, View):
    """
    Display all user goals with summary statistics
    
    WORKFLOW:
    1. Fetch all user goals ordered by deadline (earliest first)
    2. Calculate total target amount for summary card
    3. Pass to template for display
    
    LOGIC:
    - Orders by deadline to show urgent goals first
    - Template shows target amounts (progress calculated in DashboardView)
    - Provides edit/delete buttons for each goal
    """
    def get(self, request, *args, **kwargs): 
        goals = Goal.objects.filter(user=request.user).order_by('deadline')
        
        # Calculate total of all goal targets
        total_target = goals.aggregate(Sum('target_amount'))['target_amount__sum'] or 0
        
        context = {
            'goals': goals,
            'total_target': total_target,
        }
        return render(request, 'finance/goal_list.html', context)


# ============================================
# KEY PATTERNS AND REUSABLE LOGIC
# ============================================
"""
1. LoginRequiredMixin: Always add to views that need authentication
   - Redirects unauthenticated users to login page
   - Set LOGIN_URL in settings.py

2. get_object_or_404 Pattern: 
   - Always filter by user=request.user for security
   - Prevents users from accessing each other's data

3. Messages Framework:
   - Use messages.success() after create/update/delete
   - Display messages in base template

4. Form Handling Pattern:
   - GET: Create empty form or form with instance
   - POST: Validate, save, redirect on success or re-render with errors

5. Commit=False Pattern:
   - Use when you need to add user or modify data before saving
   - Then call save() explicitly

6. Aggregate Queries:
   - Use .aggregate(Sum('field')) for totals
   - Always add 'or 0' to handle None results

7. Redirect After POST:
   - Always redirect after successful POST (Post/Redirect/Get pattern)
   - Prevents duplicate form submissions

8. Template Context:
   - Pass only what's needed to templates
   - Use descriptive variable names

9. URL Naming Convention:
   - Use consistent names: 'model_list', 'model_add', 'model_edit', 'model_delete'
   - Makes templates easier to maintain

10. Reusability Tips:
    - Transaction and Goal follow same CRUD pattern
    - Copy-paste and rename model/view/form for new features
    - Same template structure can be reused
"""