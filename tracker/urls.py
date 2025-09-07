
"""
URL configuration for the tracker app.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('address/<str:address>/', views.address_detail, name='address_detail'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('add-address/', views.add_address, name='add_address'),
    path('create-watchlist/', views.create_watchlist, name='create_watchlist'),
    path('api/address/<str:address>/balance/', views.api_address_balance, name='api_address_balance'),
    path('register/', views.register, name='register'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/preferences/', views.notification_preferences, name='notification_preferences'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/notifications/count/', views.get_notification_count, name='notification_count'),

    # Authentication URLs
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]

