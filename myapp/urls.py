from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('accounts/login/', views.login_view),

    path('user/', views.user_dashboard, name='user_dashboard'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('view-requests/', views.view_requests, name='view_requests'),
    path('view-balance/', views.view_balance, name='view_balance'),


    path("admin_page/", views.pending_requests, name="dashboard"),
    path("admin_page/approve-leave/<int:leave_id>/", views.approve_leave, name="approve_leave"),
    path("admin_page/reject-leave/<int:leave_id>/", views.reject_leave, name="reject_leave"),

    path("admin_page/define-leave/", views.define_leave, name="define_leave"),
    path("admin_page/set-limits/", views.set_leave_limits, name="set_limits"),
    path("admin_page/reports/", views.leave_reports, name="view_reports"),
]
