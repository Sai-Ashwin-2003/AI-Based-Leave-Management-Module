import pandas as pd
from datetime import datetime
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache

from .models import LeaveType, LeaveRequest, LeaveBalance, CustomUser
from .utils import calculate_leave_balance

User = get_user_model()  # Use CustomUser throughout

# ---------------- AUTH / DASHBOARD ---------------- #

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@never_cache
def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            role = user.role
            if request.user.is_superuser:
                return redirect("dashboard")
            elif role == "manager":
                return redirect("manager_dashboard")
            else:
                return redirect("user_dashboard")
        else:
            return render(request, "myapp/login.html", {"error": "Invalid credentials"})

    return render(request, "myapp/login.html")


@login_required
def user_dashboard(request):
    return render(request, "myapp/user_dashboard.html")


# ---------------- LEAVE APPLICATION ---------------- #

@login_required
def apply_leave(request):
    leave_types = LeaveType.objects.all()

    if request.method == "POST":
        leave_type_id = request.POST['leave_type']
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        reason = request.POST['reason']

        leave_type = get_object_or_404(LeaveType, id=leave_type_id)

        leave_balance = calculate_leave_balance(request.user, leave_type)
        remaining_days = leave_balance['remaining']

        requested_days = (datetime.strptime(end_date, "%Y-%m-%d") -
                          datetime.strptime(start_date, "%Y-%m-%d")).days + 1

        if remaining_days <= 0:
            messages.error(request, f"You have no remaining {leave_type.name} leave.")
            return redirect('apply_leave')
        elif requested_days > remaining_days:
            messages.error(request, f"You only have {remaining_days} days left for {leave_type.name} leave.")
            return redirect('apply_leave')

        LeaveRequest.objects.create(
            user=request.user,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='Pending'
        )
        messages.success(request, "Leave request submitted.")

    return render(request, "myapp/apply_leave.html", {"leave_types": leave_types})


@login_required
def view_requests(request):
    requests = LeaveRequest.objects.filter(user=request.user).order_by('-applied_at')
    return render(request, "myapp/view_requests.html", {"requests": requests})


@login_required
def view_balance(request):
    leave_types = LeaveType.objects.all()
    balances = {lt.name: calculate_leave_balance(request.user, lt) for lt in leave_types}
    return render(request, "myapp/view_balance.html", {"balances": balances})


# ---------------- HR VIEWS ---------------- #

@login_required
def pending_requests(request):
    requests = LeaveRequest.objects.filter(status='Pending').order_by('-applied_at')
    return render(request, "myapp/admin_page.html", {"requests": requests})

@login_required
def review_leave_request(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)

    # previous leaves of same type
    previous_leaves = LeaveRequest.objects.filter(
        user=leave.user,
        leave_type=leave.leave_type
    ).exclude(id=leave.id)

    # remaining balance
    remaining_balance = calculate_leave_balance(leave.user, leave.leave_type)

    if request.method == "POST":
        action = request.POST.get("action")
        review_reason = request.POST.get("review_reason")

        if not review_reason:
            messages.error(request, "Please provide a reason.")
            return redirect("review_leave_request", leave_id=leave.id)

        if action == "accept":
            leave.status = "Approved"
        elif action == "reject":
            leave.status = "Rejected"

        leave.review_reason = review_reason
        leave.reviewed_by = request.user
        leave.save()

        messages.success(request, f"Leave {action}ed successfully.")
        return redirect("dashboard")

    return render(request, "myapp/review_leave_request.html", {
        "leave": leave,
        "previous_leaves": previous_leaves,
        "remaining_balance": remaining_balance,
    })


@login_required
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    if leave.status != 'Approved':
        leave.status = 'Approved'
        leave.save()
        calculate_leave_balance(leave.user, leave.leave_type)
        messages.success(request, f"{leave.user.username}'s leave approved. Balance updated.")
    else:
        messages.info(request, "Leave is already approved.")
    return redirect('dashboard')


@login_required
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)
    leave.status = 'Rejected'
    leave.save()
    return redirect('dashboard')


@login_required
def define_leave(request):
    if request.method == "POST":
        name = request.POST.get("name")
        yearly_limit = request.POST.get("yearly_limit")

        if name and yearly_limit:
            LeaveType.objects.update_or_create(
                name=name,
                defaults={"yearly_limit": yearly_limit}
            )
            return redirect("define_leave")

    leave_types = LeaveType.objects.all()
    return render(request, "myapp/define_leave.html", {"leave_types": leave_types})


@login_required
def set_leave_limits(request):
    leave_types = LeaveType.objects.all()

    if request.method == "POST":
        for lt in leave_types:
            new_limit = request.POST.get(f"limit_{lt.id}")
            if new_limit is not None:
                lt.yearly_limit = int(new_limit)
                lt.save()
        return redirect("set_limits")

    return render(request, "myapp/set_limits.html", {"leaves": leave_types})


# Level 1: Show links for Managers and Employees
@login_required
def leave_reports(request):
    return render(request, "myapp/view_reports.html")

# Level 2: Show list of users by role
@login_required
def list_users(request, role):
    if role not in ["manager", "employee"]:
        return render(request, "myapp/view_reports.html")  # fallback if invalid role

    users = CustomUser.objects.filter(is_superuser=False, role=role)
    return render(request, "myapp/list_users.html", {"users": users, "role": role})

# Level 3: Show detailed leave report for a single user
@login_required
def user_report(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id, is_superuser=False)
    leave_types = LeaveType.objects.all()

    report = {
        "employee": user,
        "balances": {lt.name: calculate_leave_balance(user, lt) for lt in leave_types},
    }

    return render(request, "myapp/user_report.html", {"report": report})



# ---------------- MANAGER VIEWS ---------------- #

@login_required
def manager_dashboard(request):
    # Only get employees under this manager
    employees_under_manager = CustomUser.objects.filter(manager=request.user)

    # Fetch pending requests for these employees
    pending_requests = LeaveRequest.objects.filter(
        status='Pending',
        user__in=employees_under_manager
    ).order_by('-applied_at')

    return render(request, "myapp/manager_dashboard.html", {"pending_requests": pending_requests})


@login_required
def manager_apply_leave(request):
    leave_types = LeaveType.objects.all()

    if request.method == "POST":
        leave_type_id = request.POST['leave_type']
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        reason = request.POST['reason']

        leave_type = get_object_or_404(LeaveType, id=leave_type_id)
        leave_balance = calculate_leave_balance(request.user, leave_type)
        remaining_days = leave_balance['remaining']

        requested_days = (datetime.strptime(end_date, "%Y-%m-%d") -
                          datetime.strptime(start_date, "%Y-%m-%d")).days + 1

        if remaining_days <= 0:
            messages.error(request, f"You have no remaining {leave_type.name} leave.")
            return redirect('manager_apply_leave')
        elif requested_days > remaining_days:
            messages.error(request, f"You only have {remaining_days} days left for {leave_type.name} leave.")
            return redirect('manager_apply_leave')

        LeaveRequest.objects.create(
            user=request.user,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='Pending'
        )
        messages.success(request, "Leave request submitted.")
        return redirect('manager_dashboard')

    return render(request, "myapp/manager_apply_leave.html", {"leave_types": leave_types})


@login_required
def manager_view_requests(request):
    leave_requests = LeaveRequest.objects.filter(user=request.user).order_by('-applied_at')
    return render(request, "myapp/manager_view_requests.html", {"leave_requests": leave_requests})


@login_required
def manager_approve_leave(request, request_id):
    leave = get_object_or_404(LeaveRequest, id=request_id, status="Pending")
    leave.status = "Approved"
    leave.save()
    calculate_leave_balance(leave.user, leave.leave_type)
    messages.success(request, f"Leave approved for {leave.user.username}.")
    return redirect("manager_view_requests")


@login_required
def manager_reject_leave(request, request_id):
    leave = get_object_or_404(LeaveRequest, id=request_id, status="Pending")
    leave.status = "Rejected"
    leave.save()
    messages.info(request, f"Leave rejected for {leave.user.username}.")
    return redirect("manager_view_requests")


@login_required
def manager_reports(request):
    print(request.user.username, request.user.role)

    # if request.user.role != "manager":
    #     return HttpResponseForbidden("You are not authorized to view this page.")

    employees = CustomUser.objects.filter(role="employee", manager=request.user)
    leave_types = LeaveType.objects.all()
    report = []

    for emp in employees:
        emp_data = {
            'employee': emp,
            'balances': {lt.name: calculate_leave_balance(emp, lt) for lt in leave_types}
        }
        report.append(emp_data)

    return render(request, "myapp/manager_reports.html", {"reports": report})


@login_required
def manager_leave_balance(request):
    leave_types = LeaveType.objects.all()
    balances = {lt.name: calculate_leave_balance(request.user, lt) for lt in leave_types}
    return render(request, "myapp/manager_leave_balance.html", {"balances": balances})
