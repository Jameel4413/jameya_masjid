from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from donation.models import (
    WeeklyIncome,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    EidCollection,
)


class ApiEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            username="staff_admin",
            password="adminpassword123",
            is_staff=True,
        )
        self.token = Token.objects.create(user=self.staff_user)

    def test_ping_endpoint(self):
        """Test ping endpoint both at /ping/ and /api/ping/"""
        res1 = self.client.get("/ping/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["status"], "ok")

        res2 = self.client.get("/api/ping/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["status"], "ok")

    def test_login_flow(self):
        """Test login returns token and user payload"""
        response = self.client.post("/api/auth/login/", {
            "username": "staff_admin",
            "password": "adminpassword123",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertIn("user", response.data)
        self.assertEqual(response.data["user"]["username"], "staff_admin")

    def test_me_and_authenticated_access(self):
        """Test /api/auth/me/ with Token auth"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "staff_admin")

    def test_meta_endpoint(self):
        """Test /api/meta/ returns choice tuples"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/meta/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("day_types", response.data)
        self.assertIn("expense_categories", response.data)

    def test_dashboard_endpoint(self):
        """Test /api/dashboard/ returns summary metrics"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_balance_in_hand", response.data)
        self.assertIn("grand_total_income", response.data)
        self.assertIn("recent_incomes", response.data)

    def test_weekly_income_crud_and_batch(self):
        """Test income CRUD and batch creation"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        # Batch create
        res = self.client.post("/api/incomes/batch/", [
            {"date": "2026-10-23", "day_type": "FRIDAY", "amount": "5000.00", "notes": "Test Juma"},
            {"date": "2026-10-22", "day_type": "THURSDAY", "amount": "2000.00", "notes": "Test Thursday"},
        ], format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["created"], 2)

        # List
        list_res = self.client.get("/api/incomes/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertIn("results", list_res.data)
        self.assertIn("total_collected", list_res.data)

    def test_expense_crud_and_batch(self):
        """Test expense CRUD and batch creation"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        res = self.client.post("/api/expenses/batch/", [
            {"date": "2026-10-24", "description": "Electric bill", "amount": "1200.00", "category": "UTILITIES"},
        ], format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        list_res = self.client.get("/api/expenses/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertIn("total_expenses", list_res.data)
