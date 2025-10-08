from django.core.management.base import BaseCommand
from datetime import date, timedelta
from myapp.models import UserData
import requests
import os

class Command(BaseCommand):
    help = "Update each user's 'dates' field with the dates they appeared in the API results (Jan till now)"

    def handle(self, *args, **options):
        key = os.environ.get("SPARK_FINCH_KEY")
        url = "https://aimanager.techjays.com/app/api/non-compliance/users/jaysone"
        headers = {"token": key}

        start_date = date(2025, 1, 1)
        today = date.today()
        current_date = start_date

        self.stdout.write(self.style.WARNING("Updating users' dates from January till today..."))

        updated_count = 0
        skipped_dates = 0

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

                        try:
                            obj = UserData.objects.get(user_id=user_id)
                            if formatted_date not in obj.dates:
                                obj.dates.append(formatted_date)
                                obj.save(update_fields=["dates"])
                                updated_count += 1
                        except UserData.DoesNotExist:
                            # Skip users not already stored
                            continue

                else:
                    skipped_dates += 1
                    self.stdout.write(f"Skipped {formatted_date}, status: {response.status_code}")

            except Exception as e:
                skipped_dates += 1
                self.stdout.write(f"Error fetching {formatted_date}: {e}")

            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(
            f"✅ Completed! Updated {updated_count} user-date entries. Skipped {skipped_dates} days."
        ))
