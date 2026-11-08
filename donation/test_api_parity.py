"""
API tests for the behaviour the mobile app relies on (website parity).
Run:  python manage.py test donation.test_api_parity
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import (
    EidCollection,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    WeeklyIncome,
)


class ApiParityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("staff", password="secret12", is_staff=True, first_name="Ali", last_name="Khan")
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # ---- auth -----------------------------------------------------------
    def test_login_returns_full_name(self):
        self.client.credentials()
        res = self.client.post("/api/auth/login/", {"username": "staff", "password": "secret12"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["user"]["full_name"], "Ali Khan")

    # ---- batch income / expense ------------------------------------------
    def test_income_batch_entries_creates_rows_with_urdu(self):
        body = {
            "date": "2026-07-31",
            "entries": [
                {"day_type": "FRIDAY", "amount": 5000, "notes": "juma"},
                {"day_type": "THURSDAY", "amount": 1200, "notes": ""},
            ],
        }
        res = self.client.post("/api/weekly-incomes/batch/", body, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["created"], 2)
        self.assertEqual(WeeklyIncome.objects.count(), 2)
        row = WeeklyIncome.objects.get(day_type="FRIDAY")
        self.assertEqual(row.date, date(2026, 7, 31))
        self.assertTrue(row.notes_ur)  # save() ran, so the Urdu text exists for the PDF

    def test_income_batch_rejects_empty(self):
        res = self.client.post("/api/weekly-incomes/batch/", {"date": "2026-07-31", "entries": []}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_expense_batch_entries(self):
        body = {"date": "2026-07-10", "entries": [{"category": "REPAIR", "description": "pankha", "amount": 800}]}
        res = self.client.post("/api/expenses/batch/", body, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Expense.objects.get().category, "REPAIR")

    def test_expense_category_filter_and_no_default_year(self):
        Expense.objects.create(date=date(2020, 1, 5), description="a", amount=10, category="REPAIR")
        Expense.objects.create(date=date(2020, 1, 6), description="b", amount=20, category="OTHER")
        res = self.client.get("/api/expenses/", {"category": "REPAIR", "month": "all"})
        self.assertEqual(len(res.data["results"]), 1)

    # ---- imam salary -------------------------------------------------------
    def _salary(self, **extra):
        body = {"imam_name": "Qari", "month_year": "2026-07", "total_salary": 20000}
        body.update(extra)
        return self.client.post("/api/imam-salaries/", body, format="json")

    def test_salary_accepts_year_month_and_defaults_yearly(self):
        res = self._salary()
        self.assertEqual(res.status_code, 201, res.data)
        s = ImamSalary.objects.get()
        self.assertEqual(s.month_year, date(2026, 7, 1))
        self.assertEqual(s.yearly_salary, Decimal("200000.00"))

    def test_salary_first_payment_full_and_installment(self):
        self._salary(payment_type="full", payment_date="2026-07-02")
        self.assertEqual(ImamSalaryInstallment.objects.get().amount_paid, Decimal("20000.00"))
        ImamSalaryInstallment.objects.all().delete()
        ImamSalary.objects.all().delete()
        self._salary(payment_type="installment", initial_amount_paid=5000, notes="pehli")
        inst = ImamSalaryInstallment.objects.get()
        self.assertEqual(inst.amount_paid, Decimal("5000.00"))
        self.assertIn("Qist", inst.notes)

    def test_installment_full_pays_remaining_and_caps(self):
        self._salary()
        salary = ImamSalary.objects.get()
        self.client.post("/api/imam-salary-installments/", {"salary": salary.id, "amount_paid": 8000}, format="json")
        res = self.client.post(
            "/api/imam-salary-installments/", {"salary": salary.id, "payment_type": "full"}, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(str(res.data["amount_paid"])), Decimal("12000.00"))
        # already fully paid -> refused
        res = self.client.post(
            "/api/imam-salary-installments/", {"salary": salary.id, "amount_paid": 1}, format="json"
        )
        self.assertEqual(res.status_code, 400)

    # ---- land lease -----------------------------------------------------------
    def test_lease_payment_is_capped_and_old_leases_listed(self):
        lease = LandLease.objects.create(
            tenant_name="Thekedar", start_date=date(2020, 1, 1), end_date=date(2030, 1, 1),
            duration_years=10, total_agreed_amount=1000,
        )
        res = self.client.post(
            "/api/lease-payments/", {"lease": lease.id, "payment_date": "2026-01-01", "amount_received": 5000}, format="json"
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(LandLeasePayment.objects.get().amount_received, Decimal("1000.00"))
        listing = self.client.get("/api/land-leases/", {"month": "all"})
        self.assertEqual(len(listing.data["results"]), 1)  # started in 2020, still visible

    # ---- urdu --------------------------------------------------------------
    def test_urdu_suggest(self):
        res = self.client.get("/api/urdu-suggest/", {"text": "ali"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["urdu"])

    def test_eid_urdu_approval_is_kept(self):
        body = {
            "eid_name": "EID_UL_FITR", "date": "2026-03-20", "imam_name": "ali",
            "imam_name_ur": "علی", "imam_type": "Qari Abbas", "amount_collected": 1000,
        }
        res = self.client.post("/api/eid-collections/", body, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(EidCollection.objects.get().imam_name_ur, "علی")
