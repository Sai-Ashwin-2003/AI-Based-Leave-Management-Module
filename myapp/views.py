import pandas as pd
import os
from datetime import datetime
from django.contrib.auth import authenticate, login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.cache import never_cache
import json
import requests
from datetime import date, timedelta, datetime
from .models import LeaveType, LeaveRequest, LeaveBalance, CustomUser, Project, ProjectMember, Notification, UserData, \
    ChatHistory
from .utils import calculate_leave_balance, chat_with_ai
from dotenv import load_dotenv
import os

load_dotenv()  # loads variables from .env

key = os.environ.get("SPARK_FINCH_KEY")
  # debug to confirm

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





# ---------------- LEAVE APPLICATION ---------------- #


@login_required
def user_dashboard(request):
    return render(request, "myapp/user_dashboard.html")


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
    # Leave balances
    leave_types = LeaveType.objects.all()
    balances = {lt.name: calculate_leave_balance(request.user, lt) for lt in leave_types}

    leave_dates = []

    # 1. Local DB leaves
    leaves = LeaveRequest.objects.filter(user=request.user, status="Approved")
    for leave in leaves:
        day = leave.start_date
        while day <= leave.end_date:
            leave_dates.append(str(day))
            day += timedelta(days=1)

    # 2. External API
    try:
        url = "https://ai-manager-6132686303.us-central1.run.app/app/api/non-compliance/users/jaysone"
        headers = {"token": key}  # replace VALUE with actual
        params = {"date": "2025-01-17", "page": 1, "page_size": 5}

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()

            # date from API (string)
            date_str = data.get("date")  # e.g., "2025-09-16"
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")

            days_counted = 0
            current_date = date_obj

            while days_counted < 7:
                current_date -= timedelta(days=1)
                # skip Saturday (5) and Sunday (6)
                if current_date.weekday() < 5:
                    days_counted += 1

            date_ = current_date
            # extract emails + date
            for item in data.get("users", []):
                email = item.get("email")
                if email == request.user.username:  # match with logged in user
                    leave_dates.append(date_.strftime("%Y-%m-%d"))  # << convert to string
    except Exception as e:
        print("API fetch failed:", e)

    return render(request, "myapp/view_balance.html", {
        "balances": balances,
        "leave_dates_json": json.dumps(leave_dates),
    })


# ---------------- HR VIEWS ---------------- #

@login_required
def pending_requests(request):
    requests = LeaveRequest.objects.filter(status='Pending').order_by('-applied_at')
    return render(request, "myapp/admin_page.html", {"requests": requests})


@login_required
def approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)

    if request.method == "POST":
        review_reason = request.POST.get("reason", "")
        leave.status = "Approved"
        leave.reviewed_by = request.user
        leave.review_reason = review_reason
        leave.save()
        calculate_leave_balance(leave.user, leave.leave_type)
        messages.success(request, f"{leave.user.username}'s leave approved.")
        return redirect("dashboard")

    # GET request: show a form to enter reason
    return render(request, "myapp/leave_review_form.html", {
        "leave": leave,
        "action": "Approve"
    })


@login_required
def reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)

    if request.method == "POST":
        review_reason = request.POST.get("reason", "")
        leave.status = "Rejected"
        leave.reviewed_by = request.user
        leave.review_reason = review_reason
        leave.save()
        messages.info(request, f"{leave.user.username}'s leave rejected.")
        return redirect("dashboard")

    # GET request: show a form to enter reason
    return render(request, "myapp/leave_review_form.html", {
        "leave": leave,
        "action": "Reject"
    })



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


from .models import ComplianceRecord
from .utils import fetch_and_store_compliance
from django.core.paginator import Paginator

@login_required
def leave_reports(request):
    return render(request, "myapp/view_reports.html")

#Non compliance users list
def user_list(request):
    users = UserData.objects.all().order_by('email')
    return render(request, 'myapp/user_non_compliance_list.html', {'users': users})

#Non compliance users detail
def user_detail(request, user_id):
    user = get_object_or_404(UserData, user_id=user_id)
    leave_dates_json = json.dumps(user.dates)
    return render(request, 'myapp/user_non_compliance_detail.html', {'user': user,"leave_dates_json": leave_dates_json})


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
    # Existing pending requests
    employees_under_manager = CustomUser.objects.filter(manager=request.user).distinct()
    # project_employees = CustomUser.objects.filter(projectmember__project__lead=request.user).distinct()
    # all_employees = (employees_under_manager | project_employees).distinct()

    pending_requests = LeaveRequest.objects.filter(
        status="Pending",
        user__in=employees_under_manager
    ).order_by("-applied_at")

    # Notifications
    notifications = request.user.notifications.filter(is_read=False).order_by("-created_at")
    notifications_list = list(notifications)
    # Mark all notifications as read (or delete if you prefer)
    notifications.update(is_read=True)  # OR notifications.delete() to remove completely
    return render(request, "myapp/manager_dashboard.html", {
        "pending_requests": pending_requests,
        "notifications": notifications_list
    })

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
def manager_approve_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id, status="Pending")

    # check authorization
    is_authorized = leave.user.manager == request.user or ProjectMember.objects.filter(user=leave.user, project__lead=request.user).exists()
    if not is_authorized:
        messages.error(request, "You are not authorized to approve this request.")
        return redirect("manager_dashboard")

    if request.method == "POST":
        review_reason = request.POST.get("reason", "")
        leave.status = "Approved"
        leave.reviewed_by = request.user
        leave.review_reason = review_reason
        leave.save()
        calculate_leave_balance(leave.user, leave.leave_type)
        messages.success(request, f"Leave approved for {leave.user.username}.")
        return redirect("manager_dashboard")

    # GET request: show form
    return render(request, "myapp/leave_review_form.html", {
        "leave": leave,
        "action": "Approve"
    })


@login_required
def manager_reject_leave(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id, status="Pending")

    is_authorized = leave.user.manager == request.user or ProjectMember.objects.filter(user=leave.user, project__lead=request.user).exists()
    if not is_authorized:
        messages.error(request, "You are not authorized to reject this request.")
        return redirect("manager_dashboard")

    if request.method == "POST":
        review_reason = request.POST.get("reason", "")
        leave.status = "Rejected"
        leave.reviewed_by = request.user
        leave.review_reason = review_reason
        leave.save()
        messages.info(request, f"Leave rejected for {leave.user.username}.")
        return redirect("manager_dashboard")

    return render(request, "myapp/leave_review_form.html", {
        "leave": leave,
        "action": "Reject"
    })


@login_required
def manager_reports(request):
    # Employees directly managed by this manager
    direct_employees = CustomUser.objects.filter(
        manager=request.user, role="employee"
    )
    # Employees from projects where this manager is the lead
    project_employees = CustomUser.objects.filter(
        projectmember__project__lead=request.user
    )

    leave_types = LeaveType.objects.all()
    def build_report(employee_queryset):
        report_list = []
        for emp in employee_queryset:
            emp_data = {
                "employee": emp,
                "balances": {
                    lt.name: calculate_leave_balance(emp, lt)
                    for lt in leave_types
                },
            }
            report_list.append(emp_data)
        return report_list

    # Prepare two reports
    direct_reports = build_report(direct_employees)
    project_reports = build_report(project_employees)

    context = {
        "direct_reports": direct_reports,
        "project_reports": project_reports,
    }
    return render(request, "myapp/manager_reports.html", context)

@login_required
def manager_leave_balance(request):
    # Leave balances
    leave_types = LeaveType.objects.all()
    balances = {lt.name: calculate_leave_balance(request.user, lt) for lt in leave_types}

    # Get all approved leave days as strings YYYY-MM-DD
    leaves = LeaveRequest.objects.filter(user=request.user, status="Approved")
    leave_dates = []
    for leave in leaves:
        day = leave.start_date
        while day <= leave.end_date:
            leave_dates.append(str(day))  # only YYYY-MM-DD
            day += timedelta(days=1)

    return render(request, "myapp/manager_leave_balance.html", {
        "balances": balances,
        "leave_dates_json": json.dumps(leave_dates),
    })


# Helper function to get project-specific manager/lead
def get_project_lead_for_user(user, project):
    """Returns project lead if the user is a member and not the lead"""
    if project.lead == user:
        return None
    return project.lead


# 🔹 Manager view: Leave Request Detail
@login_required
def manager_leave_request_detail(request, leave_id):
    from .utils import get_leave_decision_with_ai

    leave = get_object_or_404(LeaveRequest, id=leave_id)

    # 🔒 Authorization
    projects = ProjectMember.objects.filter(user=leave.user).select_related("project")
    authorized = any(mem.project.lead == request.user for mem in projects)
    if leave.user.manager == request.user:
        authorized = True

    if request.user.role != "manager" or not authorized:
        messages.error(request, "You are not authorized to view this request.")
        return redirect("manager_dashboard")

    # 📊 Leave balances
    balances = LeaveBalance.objects.filter(user=leave.user).select_related("leave_type")

    # 🧩 Prepare data summaries
    projects_with_leads = []
    project_status_summary = []
    for mem in projects:
        proj = mem.project
        projects_with_leads.append({
            "name": proj.name,
            "status": proj.status,
            "role": mem.role_in_project,
        })
        project_status_summary.append(f"{proj.name} ({proj.status})")

    leave_balance_summary = ", ".join(
        [f"{b.leave_type.name}: {b.remaining} days left" for b in balances]
    )

    previous_leaves_summary = "Employee has taken a few leaves earlier this quarter. Some were during active project phases."

    # 🧠 Get AI suggestions
    ai_suggestions = get_leave_decision_with_ai(
        employee_name=leave.user.username,
        leave_reason=leave.reason,
        leave_type=leave.leave_type.name,
        leave_start=leave.start_date,
        leave_end=leave.end_date,
        leave_balance=leave_balance_summary,
        project_status=", ".join(project_status_summary),
        previous_leaves_summary=previous_leaves_summary,
    )

    # 🎨 Render template
    return render(
        request,
        "myapp/manager_leave_request_detail.html",
        {
            "leave": leave,
            "projects": projects,
            "balances": balances,
            "ai_suggestions": ai_suggestions,
        },
    )



# 🔹 HR view: Leave Request Review (AI-enhanced)
@login_required
def review_leave_request(request, leave_id):
    from .utils import get_leave_decision_with_ai

    leave = get_object_or_404(LeaveRequest, id=leave_id)

    if request.user.role != "hr":
        messages.error(request, "You are not authorized to review this request.")
        return redirect("dashboard")

    projects = ProjectMember.objects.filter(user=leave.user).select_related("project")
    balances = LeaveBalance.objects.filter(user=leave.user).select_related("leave_type")

    projects_with_leads = []
    project_status_summary = []
    for mem in projects:
        proj = mem.project
        projects_with_leads.append({
            "name": proj.name,
            "lead": proj.lead.username if proj.lead else None,
            "status": proj.status,
            "role": mem.role_in_project
        })
        project_status_summary.append(f"{proj.name} ({proj.status})")

    leave_balance_summary = ", ".join(
        [f"{b.leave_type.name}: {b.remaining} days left" for b in balances]
    )

    # Fetch past leaves for this employee (excluding current leave)
    past_leaves = LeaveRequest.objects.filter(user=leave.user).exclude(id=leave.id).order_by('-applied_at')

    # Build summary string
    previous_leaves_summary = ""
    for l in past_leaves:
        reviewer = l.reviewed_by.username if l.reviewed_by else "N/A"
        review_reason = l.review_reason if l.review_reason else "N/A"
        previous_leaves_summary += (
            f"Leave Type: {l.leave_type.name}, Status: {l.status}, "
            f"Reason: {l.reason}, Start: {l.start_date}, End: {l.end_date}, "
            f"Reviewed By: {reviewer}, Review Reason: {review_reason}\n"
        )

    # If no past leaves, show default message
    if not previous_leaves_summary:
        previous_leaves_summary = "No previous leave records."

    ai_suggestions = get_leave_decision_with_ai(
        employee_name=leave.user.username,
        leave_reason=leave.reason,
        leave_type=leave.leave_type.name,
        leave_start=leave.start_date,
        leave_end=leave.end_date,
        leave_balance=leave_balance_summary,
        project_status=", ".join(project_status_summary),
        previous_leaves_summary=previous_leaves_summary,
    )

    return render(
        request,
        "myapp/review_leave_request.html",
        {
            "leave": leave,
            "projects": projects_with_leads,
            "balances": balances,
            "ai_suggestions": ai_suggestions,
        },
    )








@login_required
def notify_team_leads(request, leave_id):
    leave = get_object_or_404(LeaveRequest, id=leave_id)

    # Check if already notified
    if leave.leads_notified:
        messages.info(request, "All leads have already been notified.")
    else:
        projects = ProjectMember.objects.filter(user=leave.user).select_related("project")
        notified = 0

        for member in projects:
            lead = member.project.lead
            if lead and lead != leave.user.manager:  # skip if same as employee’s manager
                Notification.objects.create(
                    recipient=lead,
                    message=f"{leave.user.username} has requested leave ({leave.start_date} → {leave.end_date})."
                )
                notified += 1

        if notified:
            messages.success(request, f"Notified {notified} team lead(s).")
        else:
            messages.info(request, "No additional leads to notify.")

        # mark as notified
        leave.leads_notified = True
        leave.save()

    # Redirect back to the appropriate page
    if request.user.role == "hr":
        return redirect("review_leave_request", leave_id=leave.id)
    else:
        return redirect("manager_leave_request_detail", leave_id=leave.id)



#MOCK_API


# 🔹 1️⃣ View to list all users
@login_required
def mock_user_list(request):
    employees = CustomUser.objects.filter(role='employee').select_related('manager')
    managers = CustomUser.objects.filter(role='manager').select_related('manager')
    return render(request, "myapp/mock_user_list.html", {
        "employees": employees,
        "managers": managers,
    })


# 🔹 2️⃣ View to show details of a specific user
@login_required
def mock_user_detail(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    projects = ProjectMember.objects.filter(user=user).select_related('project', 'project__lead')
    leave_requests = LeaveRequest.objects.filter(user=user).select_related('leave_type')
    leave_balances = LeaveBalance.objects.filter(user=user).select_related('leave_type')

    context = {
        "user_obj": user,
        "manager": user.manager,
        "projects": projects,
        "leave_requests": leave_requests,
        "leave_balances": leave_balances,
    }
    return render(request, "myapp/mock_user_detail.html", context)


@login_required
def spark_finch_users(request):
    selected_date = request.GET.get("date")
    page = int(request.GET.get("page", 1))
    page_size = 20

    users_from_db = []
    pagination = {}
    total_employees = compliant_users = non_compliant_users = 0

    week_data = month_data = three_month_data = six_month_data = {}

    if selected_date:
        base_date = datetime.strptime(selected_date, "%Y-%m-%d").date()

        # Fetch from DB, auto-fetch from API if missing
        record = ComplianceRecord.objects.filter(date=base_date).first()
        if not record:
            fetch_and_store_compliance(selected_date, selected_date)
            record = ComplianceRecord.objects.filter(date=base_date).first()

        if record:
            users_list = record.users or []
            total_employees = record.total_users
            compliant_users = record.compliant_users
            non_compliant_users = record.non_compliant_users

            # Pagination
            paginator = Paginator(users_list, page_size)
            page_obj = paginator.get_page(page)
            users_from_db = [u["email"] for u in page_obj]

            pagination = {
                "previous_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
                "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
            }

        # Chart aggregations
        def fetch_range(days):
            start = base_date - timedelta(days=days - 1)
            records = ComplianceRecord.objects.filter(date__range=(start, base_date))
            total_compliant = sum(r.compliant_users for r in records)
            total_non_compliant = sum(r.non_compliant_users for r in records)
            total_users_agg = max((r.total_users for r in records), default=0)
            return {
                "compliant": total_compliant // days if days else 0,
                "non_compliant": total_non_compliant // days if days else 0,
                "total_users": total_users_agg,
            }

        week_data = fetch_range(7)
        month_data = fetch_range(30)
        three_month_data = fetch_range(90)
        six_month_data = fetch_range(180)

    return render(request, "myapp/spark_finch_users.html", {
        "selected_date": selected_date,
        "users_from_api": users_from_db,
        "page": page,
        "pagination": pagination,
        "has_previous": pagination.get("has_previous", False),
        "has_more": pagination.get("has_next", False),
        "total_employees": total_employees,
        "non_compliant_users": non_compliant_users,
        "compliant_users": compliant_users,
        "week_data": week_data,
        "month_data": month_data,
        "three_month_data": three_month_data,
        "six_month_data": six_month_data,
    })

def get_employee_context(user):
    # 1️⃣ Find all projects that the current user is a member of
    project_ids = ProjectMember.objects.filter(user=user).values_list('project_id', flat=True)

    # 2️⃣ Get the leads (manager IDs) of those projects
    project_leads = Project.objects.filter(id__in=project_ids).values_list('lead_id', flat=True)

    # 3️⃣ Get all projects led by those leads
    project_lead_ids = Project.objects.filter(lead__in=project_leads).values_list('id', flat=True)

    # 4️⃣ Get all members of those projects
    project_members = ProjectMember.objects.filter(
        project_id__in=project_lead_ids
    ).exclude(user=user).values_list('user_id', flat=True)

    users = list(CustomUser.objects.filter(id__in=project_members).values(
        'id', 'username', 'role', 'designation'
    ).distinct())

    # 5️⃣ Get leave requests of those project members
    leave_requests = list(LeaveRequest.objects.filter(
        user__id__in=project_members
    ).values(
        'id', 'user_id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at'
    ).distinct())

    current_user_projects = list(Project.objects.filter(id__in=project_ids).values(
        'id', 'name', 'description', 'status'
    ))
    self_leave_balance = list(LeaveBalance.objects.filter(user=user).values(
        'leave_type__name', 'total', 'used', 'remaining'
    ))
    current_user = list(CustomUser.objects.filter(id=user.id).values('id', 'username', 'role', 'designation'))
    self_leave_requests = list(LeaveRequest.objects.filter(user=user).values(
        'id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at',  'review_reason', 'reviewed_by'
    ))

    context={
        "current_user" : current_user,
        "current_user_projects" : current_user_projects,
        "leave_balance" : self_leave_balance,
        "self_leave_request" : self_leave_requests,
        "project_members" : users,
        "leave_requests" : leave_requests
    }
    return context

from django.db.models import Q

def get_manager_reports_context(user):
    # 1️⃣ Get direct employees (manager=user)
    direct_ids = CustomUser.objects.filter(manager=user).values_list('id', flat=True)
    project_members = ProjectMember.objects.filter(project__lead=user).values_list('user_id',flat=True)

    # 2️⃣ Get user details for direct employees only
    users = list(CustomUser.objects.filter(
        Q(id__in=direct_ids) | Q(id__in=project_members)
    ).values(
        'id', 'username', 'role', 'manager_id', 'designation'
    ).distinct())

    # 4️⃣ Leave requests — only for direct employees
    leave_requests = list(LeaveRequest.objects.filter( Q(user__id__in=direct_ids) | Q(user__id__in=project_members)).values(
        'id', 'user_id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at', 'leads_notified',
        'review_reason', 'reviewed_by_id'
    ).distinct())

    # 5️⃣ Leave balances — only for direct employees
    leave_balances = list(LeaveBalance.objects.filter(
        Q(user__id__in=direct_ids) | Q(user__id__in=project_members)
    ).values('id', 'user_id', 'leave_type_id', 'total', 'used', 'remaining').distinct())


    # 6️⃣ Projects — only those led by this manager (optional)
    projects = list(Project.objects.filter(lead=user).values(
        'id', 'name', 'description', 'status', 'lead_id'
    ))

    project_members = list(ProjectMember.objects.filter(project__lead=user).values('id','user_id','project_id','role_in_project','joined_at'))

    # 1️⃣ Find all projects that the current user is a member of
    project_ids = ProjectMember.objects.filter(user=user).values_list('project_id', flat=True)

    # 2️⃣ Get the leads (manager IDs) of those projects
    project_leads = Project.objects.filter(id__in=project_ids).values_list('lead_id', flat=True)

    # 3️⃣ Get all projects led by those leads
    project_lead_ids = Project.objects.filter(lead__in=project_leads).values_list('id', flat=True)

    # 4️⃣ Get all members of those projects
    co_working_members = ProjectMember.objects.filter(
        project_id__in=project_lead_ids
    ).exclude(user=user).values_list('user_id', flat=True)

    co_working_users = list(CustomUser.objects.filter(id__in=co_working_members).values(
        'id', 'username', 'role', 'designation'
    ).distinct())

    # 5️⃣ Get leave requests of those project members
    co_working_leave_requests = list(LeaveRequest.objects.filter(
        user__id__in=co_working_members
    ).values(
        'id', 'user_id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at'
    ).distinct())

    current_user=list(CustomUser.objects.filter(id=user.id).values('id', 'username', 'role', 'designation'))
    self_leave_balance = list(LeaveBalance.objects.filter(user=user).values(
        'leave_type__name', 'total', 'used', 'remaining'
    ))
    self_leave_requests = list(LeaveRequest.objects.filter(user=user).values(
        'id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at',  'review_reason', 'reviewed_by'
    ))

    # 🔟 Combine into context dictionary
    context = {
        "current_user" : current_user,
        "self_leave_balance" : self_leave_balance,
        "self_leave_requests" : self_leave_requests,
        "users": users,
        "leave_requests": leave_requests,
        "leave_balances": leave_balances,
        "projects": projects,
        "project_members": project_members,
        "co-workers" : co_working_users,
        "co-workers_leave_requests" : co_working_leave_requests
    }

    return context


def get_admin_reports_context(user):
    users = list(CustomUser.objects.all().values(
        'id', 'username', 'role', 'manager_id', 'designation'
    ))


    # Get all leave requests
    leave_requests = list(LeaveRequest.objects.all().values(
        'id', 'user_id', 'leave_type_id', 'start_date', 'end_date',
        'reason', 'status', 'applied_at', 'leads_notified',
        'review_reason', 'reviewed_by_id'
    ))

    # Get leave balances
    leave_balances = list(LeaveBalance.objects.all().values(
        'id', 'user_id', 'leave_type_id', 'total', 'used', 'remaining'
    ))

    # Get projects
    projects = list(Project.objects.all().values(
        'id', 'name', 'description', 'status', 'lead_id'
    ))

    # Get project members
    project_members = list(ProjectMember.objects.all().values(
        'id', 'user_id', 'project_id', 'role_in_project', 'joined_at'
    ))

    current_user = list(CustomUser.objects.filter(id=user.id).values('id', 'username', 'role', 'designation'))

    # Combine into one context dictionary
    context = {
        "current_user" : current_user,
        "users": users,
        "leave_requests": leave_requests,
        "leave_balances": leave_balances,
        "projects": projects,
        "project_members": project_members,
    }

    return context


@login_required
def chat_bot(request):
    if request.method == "POST":
        # Parse JSON from request body
        data = json.loads(request.body)
        message = data.get("message")  # now this will have the input
        role = data.get("role")


        # Get context based on role
        if role == "employee":
            context = get_employee_context(request.user)
        elif role == "manager":
            context = get_manager_reports_context(request.user)
        elif role== "hr":
            context=get_admin_reports_context(request.user)
        else:
            context={}

        previous_chats = ChatHistory.objects.filter(user=request.user).order_by('-timestamp')[:5]
        chat_history = [
            {"role": "user", "content": chat.prompt}
            for chat in reversed(previous_chats)
        ] + [
            {"role": "assistant", "content": chat.response}
            for chat in reversed(previous_chats)
        ]

        # Merge with current context
        context_data = {
            "role_context": context,
            "chat_history": chat_history,
        }

        # Convert context to JSON string
        context_json = json.dumps(context_data, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
        ai_text = chat_with_ai(message, context_json)

        ChatHistory.objects.create(
            user=request.user,
            prompt=message,
            response=ai_text
        )

        return JsonResponse({"response": ai_text})
    return None