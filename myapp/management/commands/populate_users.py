from django.core.management.base import BaseCommand
from datetime import date, timedelta
from myapp.models import UserData
import requests
import os

class Command(BaseCommand):
    help = "Populate user data from API (from January till now)"

    def handle(self, *args, **options):
        key = os.environ.get("SPARK_FINCH_KEY")
        url = "https://aimanager.techjays.com/app/api/non-compliance/users/jaysone"
        headers = {"token": key}

        start_date = date(2025, 1, 1)
        today = date.today()
        current_date = start_date
        added_count = 0

        self.stdout.write(self.style.WARNING("Fetching user data from January till now..."))

        while current_date <= today:
            formatted_date = current_date.strftime("%Y-%m-%d")
            params = {"date": formatted_date}

            try:
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    users = data.get("users", [])

                    for user in users:
                        user_id = user.get("id")
                        email = user.get("email")

                        if not user_id or not email:
                            continue

                        obj, created = UserData.objects.get_or_create(
                            user_id=user_id,
                            defaults={"email": email}
                        )
                        if created:
                            added_count += 1
                else:
                    self.stdout.write(f"Skipped {formatted_date}, status: {response.status_code}")

            except Exception as e:
                self.stdout.write(f"Error fetching {formatted_date}: {e}")

            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"Completed. {added_count} new users added."))
