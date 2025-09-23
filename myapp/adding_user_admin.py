
from myapp.models import CustomUser

# Create Managers
m1 = CustomUser.objects.create_user(username="manager1@tech.com", password="pass123", role="manager")
m2 = CustomUser.objects.create_user(username="manager2@tech.com", password="pass123", role="manager")

# Create Employees under Manager 1
e1 = CustomUser.objects.create_user(username="emp1@tech.com", password="pass123", role="employee", manager=m1)
e2 = CustomUser.objects.create_user(username="emp2@tech.com", password="pass123", role="employee", manager=m1)

# Create Employees under Manager 2
e3 = CustomUser.objects.create_user(username="emp3@tech.com", password="pass123", role="employee", manager=m2)


