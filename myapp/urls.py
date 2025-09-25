from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('accounts/login/', views.login_view),
    path("logout/", views.logout_view, name="logout"),

    # User routes
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('view-requests/', views.view_requests, name='view_requests'),
    path('view-balance/', views.view_balance, name='view_balance'),

    # Admin routes
    path("admin_page/", views.pending_requests, name="dashboard"),
    path("admin_page/review-leave/<int:leave_id>/", views.review_leave_request, name="review_leave_request"),
    path("admin_page/review-leave/<int:leave_id>/approve/", views.approve_leave, name="approve_leave"),
    path("admin_page/review-leave/<int:leave_id>/reject/", views.reject_leave, name="reject_leave"),
    path("admin_page/define-leave/", views.define_leave, name="define_leave"),
    path("admin_page/set-limits/", views.set_leave_limits, name="set_limits"),
    path("admin_page/reports/", views.leave_reports, name="view_reports"),
    path("admin_page/reports/role/<str:role>/", views.list_users, name="list_users"),
    path("admin_page/reports/user/<int:user_id>/", views.user_report, name="user_report"),

    # Manager routes
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/review-leave/<int:request_id>/', views.manager_leave_request_detail, name='manager_leave_request_detail'),
    path('manager/apply/', views.manager_apply_leave, name='manager_apply_leave'),
    path('manager/requests/', views.manager_view_requests, name='manager_view_requests'),
    path('manager/reports/', views.manager_reports, name='manager_reports'),
    path('manager/balance/', views.manager_leave_balance, name='manager_leave_balance'),

]
