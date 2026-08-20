from django.db import models
from django.utils import timezone
from django.db.models import Sum
# Create your models here.

# ==========================================
# 1. WEEKLY CHANDA COLLECTION (Thu / Fri)
# ==========================================
class WeeklyIncome(models.Model):
    DAY_CHOICES = [
        ('THURSDAY', 'Thursday Collection'),
        ('FRIDAY', 'Friday Collection'),
        ('OTHER', 'Other Collection'),
    ]

    date = models.DateField(default=timezone.now)
    day_type = models.CharField(max_length=20, choices=DAY_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total donation")
    notes = models.TextField(blank=True, null=True, help_text="Extra detail (optional)")

    def __str__(self):
        return f"{self.get_day_type_display()} - RS {self.amount} ({self.date})"


# ==========================================
# 2. GENERAL EXPENSES (Masjid Kharajaat)
# ==========================================
class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('UTILITIES', 'Electricity / Water Bills'),
        ('REPAIR', 'Repairing & Maintenance'),
        ('CLEANING', 'Cleaning & Supplies'),
        ('EVENT', 'Event / Program Expense'),
        ('OTHER', 'Other Expense'),
    ]

    date = models.DateField(default=timezone.now)
    description = models.CharField(max_length=255, help_text="What was the money spent on? (Clear detail)")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='OTHER')

    def __str__(self):
        return f"{self.description} - RS {self.amount} ({self.date})"


# ==========================================
# 3. IMAM SALARY & INSTALLMENTS
# ==========================================
class ImamSalary(models.Model):
    imam_name = models.CharField(max_length=100, default="Imam Masjid")
    month_year = models.DateField(help_text="Select month (e.g., 2026-07-01 for July 2026)")
    total_salary = models.DecimalField(max_digits=10, decimal_places=2, help_text="Per Month Total Salary")
    yearly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Per Year Total Salary")

    @property
    def effective_yearly_salary(self):
        if self.yearly_salary and float(self.yearly_salary) > 0:
            return float(self.yearly_salary)
        return float(self.total_salary) * 12

    @property
    def total_paid(self):
        # Calculate total installments paid so far
        paid = self.installments.aggregate(total=Sum('amount_paid'))['total']
        return float(paid) if paid else 0.0

    @property
    def remaining_salary(self):
        return float(self.total_salary) - self.total_paid

    @property
    def remaining_yearly_salary(self):
        return self.effective_yearly_salary - self.total_paid

    @property
    def is_fully_paid(self):
        return self.remaining_salary <= 0

    def __str__(self):
        return f"{self.imam_name} - {self.month_year.strftime('%B %Y')} (Paid: {self.total_paid}/{self.total_salary})"


class ImamSalaryInstallment(models.Model):
    salary_record = models.ForeignKey(ImamSalary, on_delete=models.CASCADE, related_name='installments')
    payment_date = models.DateField(default=timezone.now)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, help_text="Installment / Single payment amount")
    notes = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. 1st installment, advance, full pay")

    def __str__(self):
        return f"{self.salary_record.imam_name} - Paid RS {self.amount_paid} on {self.payment_date}"


# ==========================================
# 4. LAND LEASE & INSTALLMENTS (2 Acre Zameen)
# ==========================================
class LandLease(models.Model):
    land_area = models.CharField(max_length=50, default="2 Acres")
    tenant_name = models.CharField(max_length=100, help_text="Thekedar name")
    tenant_contact = models.CharField(max_length=20, blank=True, null=True, help_text="Phone number")

    start_date = models.DateField(help_text="Theka start date")
    end_date = models.DateField(help_text="Theka end date")
    duration_years = models.PositiveIntegerField(help_text="Theka duration")
    total_agreed_amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Total amount (e.g. 2,000,000)")

    @property
    def total_received(self):
        # Calculate total lease installments received so far
        received = self.payments.aggregate(total=Sum('amount_received'))['total']
        return received if received else 0

    @property
    def remaining_lease_amount(self):
        # Dynamically updates remaining unpaid amount from thekedar
        return self.total_agreed_amount - self.total_received

    def __str__(self):
        return f"{self.tenant_name} ({self.land_area}) - Remaining: RS {self.remaining_lease_amount}"


class LandLeasePayment(models.Model):
    lease = models.ForeignKey(LandLease, on_delete=models.CASCADE, related_name='payments')
    payment_date = models.DateField(default=timezone.now)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, help_text="Installment recieved")
    notes = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. Installment 1, 2, etc")

    def __str__(self):
        return f"{self.lease.tenant_name} - Received RS {self.amount_received} on {self.payment_date}"


# ==========================================
# 5. SPECIAL EID COLLECTION (Imams' Collection)
# ==========================================
class EidCollection(models.Model):
    EID_TYPE_CHOICES = [
        ('EID_UL_FITR', 'Eid-ul-Fitr'),
        ('EID_UL_ADHA', 'Eid-ul-Adha'),
    ]

    IMAM_TYPE_CHOICES = [
        ('Qari Abbas', 'Qari Abbas Imam (Jameya Masjid Ke Imam)'),
        ('Hafiz Shehzab', 'Hafiz Shehzab Imam (Chhoti Masjid Ke Imam)'),
    ]

    eid_name = models.CharField(max_length=20, choices=EID_TYPE_CHOICES)
    date = models.DateField(help_text="Eid ki tareekh")
    imam_name = models.CharField(max_length=100, help_text="Imam ka naam")
    imam_type = models.CharField(max_length=100, choices=IMAM_TYPE_CHOICES, default='RESIDENT')
    amount_collected = models.DecimalField(max_digits=10, decimal_places=2, help_text="Total eid amount")
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.get_eid_name_display()} ({self.date.year}) - {self.imam_name}: RS {self.amount_collected}"