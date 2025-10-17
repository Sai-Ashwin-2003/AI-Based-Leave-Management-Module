#utils.py
from .models import LeaveBalance, LeaveRequest
import json
import requests
from datetime import datetime, timedelta
from myapp.models import ComplianceRecord
from django.db import transaction
import os

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


import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_leave_decision_with_ai(
    employee_name,
    leave_reason,
    leave_type,
    leave_start,
    leave_end,
    leave_balance,
    project_status,
    previous_leaves_summary,
):
    """
    Generate AI suggestions for HR or Manager.
    role='hr' -> focus on leave policy, fairness, and leave trends
    role='manager' -> focus on project impact, team workload, deadlines
    """

    # Base instruction
    base_instruction = (
        "You are an AI assistant helping a {role} make leave decisions. "
        "Provide 3–4 short, concise bullet points that summarize key insights "
        "relevant to the role. Do NOT approve or reject the leave."
    )

    context = f"""
        Employee Name: {employee_name}
        Leave Type: {leave_type}
        Leave Reason: {leave_reason}
        Leave Duration: {leave_start} to {leave_end}
        Leave Balance: {leave_balance}
        Employee Projects & Status: {project_status}
        Previous Leave Summary: {previous_leaves_summary}
        """

    # Full prompt
    prompt = f"""
{base_instruction}

Here is the information:

{context}

Example output:
• Employee has sufficient leave balance.
• Recent leave applied for reason from start date to end date was reviewed by manager1@techjays.com and rejected with the previous_leaves_summary.reason
• Past leaves were mostly for valid reasons.
• Consider task coverage during absence.
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "No AI suggestions available."
    except Exception as e:
        return f"Error generating AI suggestions: {e}"


def chat_with_ai(prompt, context_data):
    context_json = json.dumps(context_data, indent=2)
    full_prompt = f"""
    "You are an intelligent assistant AI. Always format your responses using clean, semantic HTML structure with appropriate tags such as <p>, <h3>, <ul>, and <li>. Apply the provided CSS classes consistently for elegant styling and readability. Do not include <html> or <body> tags in your output. Ensure the tone remains professional, clear, and visually appealing."
    Below is JSON data of employee data:

    {context_json}

    TASK:
    - Analyze this JSON to answer the user's question directly.
    - If the question is about reasons, status, dates, etc., extract and reply naturally.
    - If the question is unrelated, respond normally.
    - Do not give generic intros.
    
    User's question:
    {prompt}
    """
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(full_prompt)
        ai_text = response.text
        return ai_text.strip() if ai_text else "No AI suggestions available."
    except Exception as e:
        return f"Error generating AI suggestions: {e}"
