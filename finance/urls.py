from django.urls import path
from finance.views import RegisterView,DashboardView,TransactionCreateView, TransactionDeleteView, TransactionEditView, TransactionListView,GoalCreateView, GoalListView, GoalEditView, GoalDeleteView    

urlpatterns = [
    path('register/',RegisterView.as_view(),name="register"),
    path('',DashboardView.as_view(),name='dashboard'),
    path('transaction/add/',TransactionCreateView.as_view(),name='transaction_add'),
    path('transaction/',TransactionListView.as_view(),name='transaction_list'),
    path('transaction/edit/<int:pk>/', TransactionEditView.as_view(), name='transaction_edit'),
    path('transaction/delete/<int:pk>/', TransactionDeleteView.as_view(), name='transaction_delete'),
    path('goal/add/',GoalCreateView.as_view(),name='goal_add'),
    path('goal/edit/<int:pk>/', GoalEditView.as_view(), name='goal_edit'),
    path('goal/delete/<int:pk>/', GoalDeleteView.as_view(), name='goal_delete'),
    path('goal/',GoalListView.as_view(),name='goal_list'),
]