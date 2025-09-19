from django.db import models
from django.contrib.auth.models import User


class LeaveType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    yearly_limit = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.yearly_limit})"


class LeaveBalance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, null=True)
    balance = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'leave_type')  # one balance per leave type per user

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name}: {self.balance}"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)  # dynamic types
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    applied_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.status})"



