from django.contrib.auth.models import User

# Employee
User.objects.create_user(
    username="emp1@example.com",
    email="emp1@example.com",
    password="emp12345"
)

# Another Employee
User.objects.create_user(
    username="emp2@example.com",
    email="emp2@example.com",
    password="emp12345"
)
