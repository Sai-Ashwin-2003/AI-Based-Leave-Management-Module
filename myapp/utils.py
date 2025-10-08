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


import requests
from datetime import datetime, timedelta
from myapp.models import ComplianceRecord
from django.db import transaction
import os

def fetch_and_store_compliance(start_date: str, end_date: str):
    key = os.environ.get("SPARK_FINCH_KEY")
    url = "https://aimanager.techjays.com/app/api/non-compliance/users/jaysone"

    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    delta = (end - start).days + 1

    for i in range(delta):
        day = start + timedelta(days=i)
        users = []
        page = 1
        while True:
            params = {"date": day.strftime("%Y-%m-%d"), "page": page, "page_size": 1000}
            r = requests.get(url, headers={"token": key}, params=params)
            if r.status_code != 200:
                break
            data = r.json()
            users.extend(data.get("users", []))
            pagination = data.get("pagination", {})
            if not pagination.get("has_next", False):
                break
            page += 1

        with transaction.atomic():
            ComplianceRecord.objects.update_or_create(
                date=day,
                defaults={
                    "total_users": data.get("total_users", 0),
                    "compliant_users": data.get("compliant_users", 0),
                    "non_compliant_users": data.get("non_compliant_users", 0),
                    "users": users,
                    "pagination": pagination
                }
            )
