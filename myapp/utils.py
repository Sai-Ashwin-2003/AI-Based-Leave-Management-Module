#utils.py

from .models import LeaveBalance, LeaveRequest

def calculate_leave_balance(user, leave_type):
    """
    Returns a dictionary with total, used, and remaining leave balance
    for a given user and leave type.
    """
    # Get or create balance for this leave type
    balance_obj, _ = LeaveBalance.objects.get_or_create(
        user=user,
        leave_type=leave_type,
        defaults={"total": leave_type.yearly_limit, "used": 0, "remaining": leave_type.yearly_limit}
    )

    # Get approved leaves for this type
    approved_leaves = LeaveRequest.objects.filter(
        user=user,
        leave_type=leave_type,
        status='Approved'
    )

    # Total used days
    used = sum(
        (leave.end_date - leave.start_date).days + 1
        for leave in approved_leaves
    )

    # Remaining balance
    remaining = max(balance_obj.total - used, 0)

    # ✅ Save back to DB so it persists
    balance_obj.used = used
    balance_obj.remaining = remaining
    balance_obj.save()

    return {
        "total": balance_obj.total,
        "used": used,
        "remaining": remaining,
    }


def get_project_manager(user, project):
    """
    Returns the project manager for a given user inside a project.
    """
    if project.lead == user:
        return None  # user is the project lead
    return project.lead
