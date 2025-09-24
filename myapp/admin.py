from .models import CustomUser, LeaveRequest, LeaveType, LeaveBalance
from django.contrib import admin

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(LeaveType)
admin.site.register(LeaveRequest)
admin.site.register(LeaveBalance)


