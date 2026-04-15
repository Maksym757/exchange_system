from django.contrib.auth.views import PasswordResetCompleteView, PasswordResetConfirmView
from django.urls import path

from .views import (
    admin_login,
    admin_password_reset,
    admin_register,
    admin_role_menu,
    enter_admin_role,
    google_auth_callback,
    google_auth_start,
    home,
    manager_page,
    order_status_update,
    orders_page,
    worker_page,
)

urlpatterns = [
    path('', home, name='home'),
    path('admin-panel/', admin_role_menu, name='admin_role_menu'),
    path('admin-panel/auth/', admin_login, name='admin_login'),
    path('admin-panel/register/', admin_register, name='admin_register'),
    path('admin-panel/password-reset/', admin_password_reset, name='admin_password_reset'),
    path('auth/google/start/', google_auth_start, name='google_auth_start'),
    path('auth/google/callback/', google_auth_callback, name='google_auth_callback'),
    path(
        'admin-panel/reset/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(
            template_name='admin_password_reset_confirm.html',
            success_url='/admin-panel/reset/done/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'admin-panel/reset/done/',
        PasswordResetCompleteView.as_view(
            template_name='admin_password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('admin-panel/role/<str:role_name>/', enter_admin_role, name='enter_admin_role'),
    path('orders/', orders_page, name='orders_page'),
    path('worker/', worker_page, name='worker_page'),
    path('manager/', manager_page, name='manager_page'),
    path('orders/<int:order_id>/status/', order_status_update, name='order_status_update'),
]
