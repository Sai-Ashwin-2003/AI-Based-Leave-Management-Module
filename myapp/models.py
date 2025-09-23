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
        related_name='employees'  # all employees under this manager
    )

    def __str__(self):
        return f"{self.username} ({self.role})"

class LeaveType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    yearly_limit = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.yearly_limit})"


class LeaveRequest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ instead of User
        on_delete=models.CASCADE
    )
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

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.status})"


class LeaveBalance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ instead of User
        on_delete=models.CASCADE
    )
    leave_type = models.ForeignKey("LeaveType", on_delete=models.CASCADE)
    total = models.IntegerField(default=0)
    used = models.IntegerField(default=0)
    remaining = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name}"


