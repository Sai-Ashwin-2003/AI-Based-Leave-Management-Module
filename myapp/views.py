from .models import LeaveRequest, LeaveBalance
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import LeaveType
from django.contrib import messages
from django.contrib.auth.models import User

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            if user.is_superuser:  # HR/Admin
                return redirect("dashboard")
            else:  # Employee
                return redirect("user_dashboard")
        else:
            return render(request, "myapp/login.html", {"error": "Invalid credentials"})

    return render(request, "myapp/login.html")



@login_required
def user_dashboard(request):
    return render(request, "myapp/user_dashboard.html")


@login_required
def apply_leave(request):
    # Fetch only leave types defined by admin
    leave_types = LeaveType.objects.all()

    if request.method == "POST":
        leave_type_id = request.POST['leave_type']  # will be the ID from <option value="{{ lt.id }}">
        start_date = request.POST['start_date']
        end_date = request.POST['end_date']
        reason = request.POST['reason']

        # Get the LeaveType instance
        leave_type = get_object_or_404(LeaveType, id=leave_type_id)

        LeaveRequest.objects.create(
            user=request.user,
            leave_type=leave_type,  # now assigning the object, not string
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status='Pending'
        )
        return redirect('view_requests')

    return render(request, "myapp/apply_leave.html", {"leave_types": leave_types})



@login_required
def view_requests(request):
    requests = LeaveRequest.objects.filter(user=request.user).order_by('-applied_at')
    return render(request, "myapp/view_requests.html", {"requests": requests})


@login_required
def view_balance(request):
    leave_types = LeaveType.objects.all()
    balances = {}

    for lt in leave_types:
        # Get or create leave balance
        balance_obj, _ = LeaveBalance.objects.get_or_create(
            user=request.user,
            leave_type=lt,
            defaults={'balance': lt.yearly_limit}
        )

        # Get all approved leaves for this leave type
        approved_leaves = LeaveRequest.objects.filter(
            user=request.user,
            leave_type=lt,
            status='Approved'
        )

        # Calculate total used days in Python
        used = sum(
            (leave.end_date - leave.start_date).days + 1
            for leave in approved_leaves
        )

        # Remaining balance
        balances[lt.name] = max(balance_obj.balance - used, 0)

    return render(request, "myapp/view_balance.html", {"balances": balances})




#admin_page_views

@login_required
def pending_requests(request):
    requests = LeaveRequest.objects.filter(status='Pending').order_by('-applied_at')
    return render(request, "myapp/admin_page.html", {"requests": requests})


@login_required
def approve_leave(request, leave_id):
    # Get the leave request
    leave = get_object_or_404(LeaveRequest, id=leave_id)

    if leave.status != 'Approved':
        leave.status = 'Approved'
        leave.save()

        # Get or create leave balance for this user and leave type
        balance, created = LeaveBalance.objects.get_or_create(
            user=leave.user,
            leave_type=leave.leave_type,
            defaults={'balance': leave.leave_type.yearly_limit}  # initial balance if new
        )

        # Calculate number of days for the leave
        days = (leave.end_date - leave.start_date).days + 1

        # Deduct days from balance safely
        balance.balance = max(balance.balance - days, 0)
        balance.save()

        messages.success(request, f"{leave.user.username}'s leave approved. Balance updated.")
    else:
        messages.info(request, "Leave is already approved.")

    return redirect('dashboard')


@login_required
def reject_leave(request, leave_id):
    leave = LeaveRequest.objects.get(id=leave_id)
    leave.status = 'Rejected'
    leave.save()
    return redirect('dashboard')



#@login_required
# @staff_member_required  # uncomment if only admins can access
def define_leave(request):
    if request.method == "POST":
        name = request.POST.get("name")
        yearly_limit = request.POST.get("yearly_limit")

        if name and yearly_limit:
            # Create new leave type or update if it already exists
            LeaveType.objects.update_or_create(
                name=name,
                defaults={"yearly_limit": yearly_limit}
            )
            return redirect("define_leave")  # reload the same page after saving

    # Get all leave types to display in the table
    leave_types = LeaveType.objects.all()
    return render(request, "myapp/define_leave.html", {"leave_types": leave_types})


@login_required
# @staff_member_required  # enable if only admins should access
def set_leave_limits(request):
    leave_types = LeaveType.objects.all()

    if request.method == "POST":
        for lt in leave_types:
            new_limit = request.POST.get(f"limit_{lt.id}")
            if new_limit is not None:
                lt.yearly_limit = int(new_limit)
                lt.save()
        return redirect("set_limits")  # reload the same page after update

    return render(request, "myapp/set_limits.html", {"leaves": leave_types})


@login_required
# @staff_member_required  # uncomment if only admins should access
def leave_reports(request):
    # Get all employees (or filter as needed)
    employees = User.objects.all()

    # Get all leave types defined by admin
    leave_types = LeaveType.objects.all()

    # Prepare a report dictionary
    report = []

    for emp in employees:
        emp_data = {
            'employee': emp,
            'balances': {}
        }

        for lt in leave_types:
            # Get or create balance for this leave type
            balance_obj, _ = LeaveBalance.objects.get_or_create(
                user=emp,
                leave_type=lt,
                defaults={'balance': lt.yearly_limit}  # admin-set limit
            )

            # Count approved leaves taken for this leave type
            used = LeaveRequest.objects.filter(
                user=emp,
                leave_type=lt,
                status='Approved'
            ).count()

            # Remaining leaves
            remaining = max(balance_obj.balance - used, 0)

            # Store in employee data
            emp_data['balances'][lt.name] = {
                'total': balance_obj.balance,
                'used': used,
                'remaining': remaining
            }

        report.append(emp_data)

    return render(request, "myapp/view_reports.html", {
        'report': report,
        'leave_types': leave_types
    })

