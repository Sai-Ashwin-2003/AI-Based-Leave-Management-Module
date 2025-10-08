from django.core.management.base import BaseCommand
from myapp.utils import fetch_and_store_compliance
from datetime import date

class Command(BaseCommand):
    help = "Fetch and store compliance data from Jan till today"

    def handle(self, *args, **kwargs):
        start_date = "2025-01-01"
        end_date = date.today().strftime("%Y-%m-%d")
        fetch_and_store_compliance(start_date, end_date)
        self.stdout.write(self.style.SUCCESS("Compliance data populated successfully!"))