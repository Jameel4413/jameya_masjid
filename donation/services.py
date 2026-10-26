from datetime import datetime
from django.db.models import Sum
from django.utils import timezone

from .models import (
    WeeklyIncome,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    EidCollection,
)


class Period:
    """Helper class to encapsulate year/month filtering period."""

    def __init__(self, year=None, month=None, is_all_months=False):
        self.year = year
        self.month = month
        self.is_all_months = is_all_months

    def __getitem__(self, item):
        return getattr(self, item, None)

    def get(self, item, default=None):
        return getattr(self, item, default)


def parse_period(query_params):
    """
    Parses request query params for year and month filters.
    Defaults to current year/month if not explicitly provided or empty.
    """
    now = timezone.now()
    year_str = query_params.get("year", "") if query_params else ""
    month_str = query_params.get("month", "") if query_params else ""

    is_all_months = (month_str == "all" or month_str == "")

    curr_year = int(year_str) if (year_str and str(year_str).isdigit()) else now.year
    curr_month = int(month_str) if (month_str and str(month_str).isdigit()) else (None if is_all_months else now.month)

    # If neither year nor month was provided at all in query_params, default to current month
    if query_params is not None and "month" not in query_params:
        curr_month = now.month
        is_all_months = False

    return Period(year=curr_year, month=curr_month, is_all_months=is_all_months)


def filter_by_month_year(queryset, date_field, period):
    """Filters a queryset by year and month from a Period object or dict."""
    if not period:
        return queryset

    year = period.year if hasattr(period, "year") else (period.get("year") if isinstance(period, dict) else None)
    month = period.month if hasattr(period, "month") else (period.get("month") if isinstance(period, dict) else None)
    is_all = getattr(period, "is_all_months", False) or (isinstance(period, dict) and period.get("is_all_months", False))

    filter_kwargs = {}
    if year:
        filter_kwargs[f"{date_field}__year"] = year
    if month and not is_all:
        filter_kwargs[f"{date_field}__month"] = month

    return queryset.filter(**filter_kwargs)


def get_all_time_totals():
    """Calculates all-time running balance: Total Weekly Income - (Expenses + Imam Salary Paid)."""
    total_weekly_income = WeeklyIncome.objects.aggregate(t=Sum("amount"))["t"] or 0
    grand_total_income = total_weekly_income

    total_expenses = Expense.objects.aggregate(t=Sum("amount"))["t"] or 0
    total_salary_paid = ImamSalaryInstallment.objects.aggregate(t=Sum("amount_paid"))["t"] or 0
    grand_total_expense = total_expenses + total_salary_paid

    return float(grand_total_income), float(grand_total_expense)


def dashboard_data(period):
    """Computes high-level dashboard metrics for the given period."""
    now = timezone.now()
    grand_total_income_all, grand_total_expense_all = get_all_time_totals()
    total_balance_in_hand = grand_total_income_all - grand_total_expense_all

    curr_year = period.year or now.year
    curr_month = period.month or now.month
    is_all_months = period.is_all_months

    prev_months_remaining = 0.0

    if not is_all_months and curr_year and curr_month:
        start_date_of_month = datetime(curr_year, curr_month, 1).date()
        prev_income = WeeklyIncome.objects.filter(date__lt=start_date_of_month).aggregate(t=Sum("amount"))["t"] or 0
        prev_expense = (
            (Expense.objects.filter(date__lt=start_date_of_month).aggregate(t=Sum("amount"))["t"] or 0)
            + (ImamSalaryInstallment.objects.filter(payment_date__lt=start_date_of_month).aggregate(t=Sum("amount_paid"))["t"] or 0)
        )
        prev_months_remaining = float(prev_income - prev_expense)

        weekly_qs = WeeklyIncome.objects.filter(date__year=curr_year, date__month=curr_month)
        expense_qs = Expense.objects.filter(date__year=curr_year, date__month=curr_month)
        salary_qs = ImamSalaryInstallment.objects.filter(payment_date__year=curr_year, payment_date__month=curr_month)

        curr_month_weekly_income = float(weekly_qs.aggregate(t=Sum("amount"))["t"] or 0)
        period_income = prev_months_remaining + curr_month_weekly_income
        period_expense = float(
            (expense_qs.aggregate(t=Sum("amount"))["t"] or 0)
            + (salary_qs.aggregate(t=Sum("amount_paid"))["t"] or 0)
        )
    else:
        weekly_qs = WeeklyIncome.objects.all()
        expense_qs = Expense.objects.all()
        salary_qs = ImamSalaryInstallment.objects.all()

        if curr_year:
            weekly_qs = weekly_qs.filter(date__year=curr_year)
            expense_qs = expense_qs.filter(date__year=curr_year)
            salary_qs = salary_qs.filter(payment_date__year=curr_year)

        period_income = float(weekly_qs.aggregate(t=Sum("amount"))["t"] or 0)
        period_expense = float(
            (expense_qs.aggregate(t=Sum("amount"))["t"] or 0)
            + (salary_qs.aggregate(t=Sum("amount_paid"))["t"] or 0)
        )

    period_net = period_income - period_expense

    recent_incomes = WeeklyIncome.objects.all().order_by("-date", "-id")[:5]
    recent_expenses = Expense.objects.all().order_by("-date", "-id")[:5]

    period_label = "Tamam Mahine" if is_all_months else (
        datetime(curr_year, curr_month, 1).strftime("%B %Y") if (curr_year and curr_month) else ""
    )

    return {
        "total_balance_in_hand": float(total_balance_in_hand),
        "grand_total_income": float(period_income),
        "grand_total_expense": float(period_expense),
        "period_net": float(period_net),
        "prev_months_remaining": float(prev_months_remaining),
        "recent_incomes": recent_incomes,
        "recent_expenses": recent_expenses,
        "selected_year": str(curr_year),
        "selected_month": "" if is_all_months else str(curr_month or ""),
        "period_label": period_label,
    }


def weekly_income_overview(period):
    """Returns queryset and summary statistics for Weekly Income."""
    now = timezone.now()
    curr_year = period.year
    curr_month = period.month
    is_all_months = period.is_all_months

    incomes = WeeklyIncome.objects.all().order_by("-date", "-id")
    prev_months_remaining = 0.0
    carryover_date = None

    if curr_month and curr_year and not is_all_months:
        incomes = incomes.filter(date__year=curr_year, date__month=curr_month)
        start_date_of_month = datetime(curr_year, curr_month, 1).date()
        carryover_date = start_date_of_month

        prev_income = WeeklyIncome.objects.filter(date__lt=start_date_of_month).aggregate(t=Sum("amount"))["t"] or 0
        prev_expense = (
            (Expense.objects.filter(date__lt=start_date_of_month).aggregate(t=Sum("amount"))["t"] or 0)
            + (ImamSalaryInstallment.objects.filter(payment_date__lt=start_date_of_month).aggregate(t=Sum("amount_paid"))["t"] or 0)
        )
        prev_months_remaining = float(prev_income - prev_expense)
    elif curr_year:
        incomes = incomes.filter(date__year=curr_year)

    current_collections = float(incomes.aggregate(total=Sum("amount"))["total"] or 0)
    total_collected = prev_months_remaining + current_collections

    summary = {
        "total_collected": total_collected,
        "current_collections": current_collections,
        "prev_months_remaining": prev_months_remaining,
        "carryover_date": carryover_date.isoformat() if carryover_date else None,
        "selected_year": str(curr_year) if curr_year else "",
        "selected_month": "" if is_all_months else (str(curr_month) if curr_month else ""),
    }
    return incomes, summary


def imam_salary_overview(query_params):
    """Returns queryset and comprehensive summary metrics for Imam Salaries."""
    now = timezone.now()
    year = query_params.get("year") if query_params else None
    month = query_params.get("month") if query_params else None

    is_default_view = not year and not month

    curr_year = int(year) if (year and str(year).isdigit()) else now.year
    curr_month = int(month) if (month and str(month).isdigit()) else now.month

    salaries = ImamSalary.objects.filter(month_year__year=curr_year)
    if is_default_view or (month and str(month).isdigit()):
        salaries = salaries.filter(month_year__month=curr_month)
    salaries = salaries.order_by("-month_year", "-id")

    total_month_salary_value = float(sum(s.total_salary for s in salaries))
    total_month_paid = float(sum(s.total_paid for s in salaries))
    total_month_remaining = float(sum(s.remaining_salary for s in salaries))

    year_salaries = ImamSalary.objects.filter(month_year__year=curr_year)
    distinct_imams = set(year_salaries.values_list("imam_name", flat=True))
    total_year_salary_value = 0.0
    for imam in distinct_imams:
        imam_latest = year_salaries.filter(imam_name=imam).order_by("-month_year").first()
        if imam_latest:
            total_year_salary_value += float(imam_latest.effective_yearly_salary)

    total_year_paid = float(sum(s.total_paid for s in year_salaries))
    total_year_remaining = max(0.0, total_year_salary_value - total_year_paid)

    summary = {
        "total_pending_salary_amount": total_month_remaining,
        "total_month_salary_value": total_month_salary_value,
        "total_month_paid": total_month_paid,
        "total_month_remaining": total_month_remaining,
        "total_year_salary_value": total_year_salary_value,
        "total_year_paid": total_year_paid,
        "total_year_remaining": total_year_remaining,
        "selected_year": str(curr_year),
        "selected_month": str(curr_month) if (is_default_view or month) else "",
        "current_period_label": datetime(curr_year, curr_month, 1).strftime("%B %Y") if (curr_year and curr_month) else "",
    }
    return salaries, summary
