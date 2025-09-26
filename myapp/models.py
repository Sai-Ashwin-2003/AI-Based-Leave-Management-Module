from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('employee', 'Employee'),
        ('manager', 'Manager'),
        ('hr', 'HR'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='employee')
    manager = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employees'
    )
    # 🔹 New field for designation/skillset
    designation = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class LeaveType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    yearly_limit = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.yearly_limit})"


class LeaveRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    leave_type = models.ForeignKey("LeaveType", on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected")],
        default="Pending"
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    leads_notified = models.BooleanField(default=False)

    # 🔹 New review fields
    review_reason = models.TextField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_leaves"
    )

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.status})"


class LeaveBalance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    leave_type = models.ForeignKey("LeaveType", on_delete=models.CASCADE)
    total = models.IntegerField(default=0)
    used = models.IntegerField(default=0)
    remaining = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name}"


# 🔹 New Project Model
class Project(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('On Hold', 'On Hold'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="led_projects"
    )

    def __str__(self):
        return f"{self.name} ({self.status})"


# 🔹 Through model for Project Members
class ProjectMember(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    role_in_project = models.CharField(max_length=100, blank=True, null=True)  # e.g. Backend Dev, Tester
    joined_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.project.name} as {self.role_in_project or 'Member'}"



# models.py
class Notification(models.Model):
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
