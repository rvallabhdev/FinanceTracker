from django.shortcuts import render, HttpResponse, redirect, get_object_or_404
from django.views import View
from finance.forms import GoalForm, RegisterForm, TransactionForm, CategoryForm
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from finance.models import Transaction, Goal, Category
from django.db.models import Sum
from django.contrib import messages
from django.db.models import Q
from datetime import datetime, timedelta


# ============================================
# USER REGISTRATION VIEW
# ============================================
class RegisterView(View):

    def get(self, request, *args, **kwargs):
        form = RegisterForm()
        return render(request, 'finance/register.html', {'form': form})

    def post(self, request, *args, **kwargs):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
        return render(request, 'finance/register.html', {'form': form})


# ============================================
# DASHBOARD VIEW
# ============================================
class DashboardView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):

        transactions = Transaction.objects.filter(user=request.user).order_by('-date')
        goals = Goal.objects.filter(user=request.user).order_by('deadline')

        total_income = Transaction.objects.filter(
            user=request.user,
            transaction_type='Income'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        total_expense = Transaction.objects.filter(
            user=request.user,
            transaction_type='Expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        net_savings = total_income - total_expense

        goal_progress = []
        remaining_savings = net_savings

        for goal in goals:
            if remaining_savings >= goal.target_amount:
                progress = 100
                remaining_savings -= goal.target_amount

            elif remaining_savings > 0:
                progress = (remaining_savings / goal.target_amount) * 100
                remaining_savings = 0

            else:
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
# TRANSACTION CREATE
# ============================================
class TransactionCreateView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        form = TransactionForm()
        categories = Category.objects.filter(user=request.user)
        return render(request, 'finance/transaction_form.html', {
            'form': form,
            'is_edit': False,
            'categories': categories
        })

    def post(self, request, *args, **kwargs):
        form = TransactionForm(request.POST)
        categories = Category.objects.filter(user=request.user)  # FIXED

        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user
            transaction.save()

            messages.success(request, f'Transaction "{transaction.title}" added successfully!')
            return redirect('transaction_list')

        return render(request, 'finance/transaction_form.html', {
            'form': form,
            'is_edit': False,
            'categories': categories
        })


# ============================================
# TRANSACTION EDIT
# ============================================
class TransactionEditView(LoginRequiredMixin, View):

    def get(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        form = TransactionForm(instance=transaction)
        categories = Category.objects.filter(user=request.user)

        return render(request, 'finance/transaction_form.html', {
            'form': form,
            'transaction': transaction,
            'is_edit': True,
            'categories': categories
        })

    def post(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        form = TransactionForm(request.POST, instance=transaction)
        categories = Category.objects.filter(user=request.user)

        if form.is_valid():
            form.save()
            messages.success(request, f'Transaction "{transaction.title}" updated successfully!')
            return redirect('transaction_list')

        return render(request, 'finance/transaction_form.html', {
            'form': form,
            'transaction': transaction,
            'is_edit': True,
            'categories': categories
        })


# ============================================
# TRANSACTION DELETE
# ============================================
class TransactionDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk, *args, **kwargs):
        transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
        title = transaction.title
        transaction.delete()

        messages.success(request, f'Transaction "{title}" deleted successfully!')
        return redirect('transaction_list')


# ============================================
# TRANSACTION LIST
# ============================================
class TransactionListView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):

        transactions = Transaction.objects.filter(user=request.user)

        search = request.GET.get('search')
        txn_type = request.GET.get('type')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if search:
            transactions = transactions.filter(
                Q(title__icontains=search) |
                Q(category__name__icontains=search)
            )

        if txn_type:
            transactions = transactions.filter(transaction_type=txn_type)

        if start_date:
            transactions = transactions.filter(date__gte=start_date)

        if end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            transactions = transactions.filter(date__lt=end_date_obj)

        transactions = transactions.order_by('-date')

        total_income = transactions.filter(
            transaction_type='Income'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        total_expense = transactions.filter(
            transaction_type='Expense'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        return render(request, 'finance/transaction_list.html', {
            'transactions': transactions,
            'total_income': total_income,
            'total_expense': total_expense,
        })


# ============================================
# CATEGORY CRUD (ADDED)
# ============================================
class CategoryListView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        categories = Category.objects.filter(user=request.user)
        return render(request, "finance/category_list.html", {
            "categories": categories
        })


class CategoryCreateView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        form = CategoryForm()
        return render(request, "finance/category_form.html", {
            "form": form
        })

    def post(self, request, *args, **kwargs):
        form = CategoryForm(request.POST)

        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()

            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect("category_list")

        return render(request, "finance/category_form.html", {
            "form": form
        })


class CategoryUpdateView(LoginRequiredMixin, View):

    def get(self, request, pk, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk, user=request.user)
        form = CategoryForm(instance=category)

        return render(request, "finance/category_form.html", {
            "form": form,
            "category": category
        })

    def post(self, request, pk, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk, user=request.user)
        form = CategoryForm(request.POST, instance=category)

        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect("category_list")

        return render(request, "finance/category_form.html", {
            "form": form,
            "category": category
        })


class CategoryDeleteView(LoginRequiredMixin, View):

    def post(self, request, pk, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk, user=request.user)
        name = category.name
        category.delete()

        messages.success(request, f'Category "{name}" deleted successfully!')
        return redirect("category_list")


# ============================================
# GOAL VIEWS
# ============================================
class GoalCreateView(LoginRequiredMixin, View):

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
            return redirect('dashboard')

        return render(request, 'finance/goal_form.html', {'form': form})


class GoalEditView(LoginRequiredMixin, View):

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

    def post(self, request, pk, *args, **kwargs):
        goal = get_object_or_404(Goal, pk=pk, user=request.user)
        name = goal.name
        goal.delete()

        messages.success(request, f'Goal "{name}" deleted successfully!')
        return redirect('dashboard')


class GoalListView(LoginRequiredMixin, View):

    def get(self, request, *args, **kwargs):

        goals = Goal.objects.filter(user=request.user).order_by('deadline')
        total_target = goals.aggregate(Sum('target_amount'))['target_amount__sum'] or 0

        return render(request, 'finance/goal_list.html', {
            'goals': goals,
            'total_target': total_target,
        })
    
# Add these at the bottom of your finance/views.py file, after all your existing views

# ============================================
# EXPORT VIEWS (Redirect to csvhandler)
# ============================================
class ExportOptionsView(LoginRequiredMixin, View):
    """Redirect to csvhandler export options"""
    
    def get(self, request, *args, **kwargs):
        from django.urls import reverse
        return redirect(reverse('csvhandler:export_options'))


class ExportTransactionsView(LoginRequiredMixin, View):
    """Redirect to csvhandler export transactions"""
    
    def get(self, request, *args, **kwargs):
        from django.urls import reverse
        # Preserve any query parameters
        url = reverse('csvhandler:export_transactions_csv')
        if request.GET:
            url += '?' + request.GET.urlencode()
        return redirect(url)