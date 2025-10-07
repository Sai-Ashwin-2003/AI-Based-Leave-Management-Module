from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
import requests, os
from myapp.models import ComplianceRecord

class Command(BaseCommand):
    help = "Load compliance data for all previous dates from API"

    def handle(self, *args, **kwargs):
        key = os.environ.get("SPARK_FINCH_KEY")
        url = "https://ai-manager-6132686303.us-central1.run.app/app/api/non-compliance/users/jaysone"
        headers = {"token": key}

        today = datetime.today().date()
        days_to_fetch = 180  # or however many days you want

        for i in range(days_to_fetch):
            day = today - timedelta(days=i)
            params = {"date": day.strftime("%Y-%m-%d"), "page": 1, "page_size": 20}

            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                d = response.json()

                ComplianceRecord.objects.update_or_create(
                    date=day,
                    defaults={
                        "total_users": d.get("total_users", 0),
                        "compliant_users": d.get("compliant_users", 0),
                        "non_compliant_users": d.get("non_compliant_users", 0),
                        "users": d.get("users", []),
                        "pagination": d.get("pagination", {}),
                    },
                )
                print(f"✅ Stored record for {day}")
            else:
                print(f"⚠️ Failed to fetch {day}: {response.status_code}")
