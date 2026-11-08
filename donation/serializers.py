import re
from decimal import Decimal

from django.contrib.auth.models import User  # noqa: F401  (kept for backwards compatibility)
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from .models import (
    WeeklyIncome,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    EidCollection,
)
from .urdu_input import composed_ur, resolve


def user_payload(user):
    """Returns standardized user payload for auth endpoints."""
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    full_name = f"{first} {last}".strip()
    return {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", "") or "",
        "first_name": first,
        "last_name": last,
        # The Flutter app shows this in Settings ("Signed in as ...").
        "full_name": full_name or user.username,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


# ==========================================================================
# Shared helpers
# ==========================================================================
class MonthYearDateField(serializers.DateField):
    """Accepts both "2026-07-15" and the month picker's "2026-07"."""

    def to_internal_value(self, value):
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{1,2}", value.strip()):
            year, month = value.strip().split("-")
            value = f"{int(year):04d}-{int(month):02d}-01"
        return super().to_internal_value(value)


class UrduApprovalMixin:
    """
    Same "Roman Urdu in -> approved Urdu out" flow the website forms use.

    For every (roman_field, urdu_field) pair: when the Roman text is part of the
    request, the stored Urdu is either what the user approved in the app (and the
    corrections are learnt into WordMapping) or the transliteration engine's
    suggestion.  Works for partial (PATCH) updates too.
    """

    URDU_PAIRS = ()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        for roman_field, urdu_field in self.URDU_PAIRS:
            if roman_field in attrs:
                attrs[urdu_field] = resolve(attrs.get(roman_field) or "", attrs.get(urdu_field) or "")
        return attrs


# ==========================================================================
# Auth Serializers
# ==========================================================================
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)


# ==========================================================================
# Weekly Income Serializers
# ==========================================================================
class WeeklyIncomeSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("notes", "notes_ur"),)
    day_type_display = serializers.CharField(source="get_day_type_display", read_only=True)

    class Meta:
        model = WeeklyIncome
        fields = [
            "id",
            "date",
            "day_type",
            "day_type_display",
            "amount",
            "notes",
            "notes_ur",
        ]


class IncomeEntrySerializer(UrduApprovalMixin, serializers.Serializer):
    """One row of the "add chanda" form (the date is shared by all rows)."""

    URDU_PAIRS = (("notes", "notes_ur"),)

    day_type = serializers.ChoiceField(choices=WeeklyIncome.DAY_CHOICES, default="OTHER")
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, default="")
    notes_ur = serializers.CharField(required=False, allow_blank=True, default="")


class IncomeBatchSerializer(serializers.Serializer):
    """
    Preferred body (what the mobile app sends):
        {"date": "2026-07-31", "entries": [{"day_type": "FRIDAY", "amount": 5000, "notes": ""}]}
    Still accepted for older clients: a plain list, or {"items": [{... "date": ...}]}.
    """

    date = serializers.DateField(required=False)
    entries = IncomeEntrySerializer(many=True, required=False)
    items = WeeklyIncomeSerializer(many=True, required=False)

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"items": data}
        return super().to_internal_value(data)

    def validate(self, attrs):
        entries = attrs.get("entries") or []
        items = attrs.get("items") or []
        if not entries and not items:
            raise serializers.ValidationError({"entries": "Kam az kam ek entry bhejein."})
        if entries and not attrs.get("date"):
            raise serializers.ValidationError({"date": "Tareekh lazmi hai."})
        return attrs

    def create(self, validated_data):
        created = []
        day = validated_data.get("date")
        # .create() (not bulk_create) on purpose: model.save() fills the Urdu text for the PDF.
        with transaction.atomic():
            for entry in validated_data.get("entries") or []:
                created.append(WeeklyIncome.objects.create(date=day, **entry))
            for item in validated_data.get("items") or []:
                created.append(WeeklyIncome.objects.create(**item))
        return created


# ==========================================================================
# Expense Serializers
# ==========================================================================
class ExpenseSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("description", "description_ur"),)
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "date",
            "description",
            "description_ur",
            "amount",
            "category",
            "category_display",
        ]


class ExpenseEntrySerializer(UrduApprovalMixin, serializers.Serializer):
    URDU_PAIRS = (("description", "description_ur"),)

    category = serializers.ChoiceField(choices=Expense.CATEGORY_CHOICES, default="OTHER")
    description = serializers.CharField(max_length=255)
    description_ur = serializers.CharField(required=False, allow_blank=True, default="", max_length=500)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))


class ExpenseBatchSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    entries = ExpenseEntrySerializer(many=True, required=False)
    items = ExpenseSerializer(many=True, required=False)

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"items": data}
        return super().to_internal_value(data)

    def validate(self, attrs):
        entries = attrs.get("entries") or []
        items = attrs.get("items") or []
        if not entries and not items:
            raise serializers.ValidationError({"entries": "Kam az kam ek kharcha bhejein."})
        if entries and not attrs.get("date"):
            raise serializers.ValidationError({"date": "Tareekh lazmi hai."})
        return attrs

    def create(self, validated_data):
        created = []
        day = validated_data.get("date")
        with transaction.atomic():
            for entry in validated_data.get("entries") or []:
                created.append(Expense.objects.create(date=day, **entry))
            for item in validated_data.get("items") or []:
                created.append(Expense.objects.create(**item))
        return created


# ==========================================================================
# Eid Collection Serializer
# ==========================================================================
class EidCollectionSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("imam_name", "imam_name_ur"), ("notes", "notes_ur"))
    eid_name_display = serializers.CharField(source="get_eid_name_display", read_only=True)
    imam_type_display = serializers.CharField(source="get_imam_type_display", read_only=True)

    class Meta:
        model = EidCollection
        fields = [
            "id",
            "eid_name",
            "eid_name_display",
            "date",
            "imam_name",
            "imam_name_ur",
            "imam_type",
            "imam_type_display",
            "amount_collected",
            "notes",
            "notes_ur",
        ]


# ==========================================================================
# Land Lease Serializers
# ==========================================================================
class LandLeasePaymentSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("notes", "notes_ur"),)
    tenant_name = serializers.CharField(source="lease.tenant_name", read_only=True)

    class Meta:
        model = LandLeasePayment
        fields = [
            "id",
            "lease",
            "tenant_name",
            "payment_date",
            "amount_received",
            "notes",
            "notes_ur",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        lease = attrs.get("lease") or (self.instance.lease if self.instance else None)
        amount = attrs.get("amount_received")
        if lease is not None and amount is not None:
            others = lease.payments.all()
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            already = others.aggregate(t=Sum("amount_received"))["t"] or Decimal("0")
            max_allowed = lease.total_agreed_amount - already
            if max_allowed <= 0:
                raise serializers.ValidationError(
                    {"amount_received": "Is theke ki poori raqam pehle hi wasool ho chuki hai."}
                )
            # Same rule as the website: never record more than what is actually remaining.
            attrs["amount_received"] = min(amount, max_allowed)
        return attrs


class LandLeaseSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("tenant_name", "tenant_name_ur"),)
    payments = LandLeasePaymentSerializer(many=True, read_only=True)
    total_received = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_lease_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LandLease
        fields = [
            "id",
            "land_area",
            "tenant_name",
            "tenant_name_ur",
            "tenant_contact",
            "start_date",
            "end_date",
            "duration_years",
            "total_agreed_amount",
            "total_received",
            "remaining_lease_amount",
            "payments",
        ]


# ==========================================================================
# Imam Salary Serializers
# ==========================================================================
class ImamSalaryInstallmentSerializer(UrduApprovalMixin, serializers.ModelSerializer):
    """Read + edit of an existing installment (the website's "update payment" form)."""

    URDU_PAIRS = (("notes", "notes_ur"),)
    imam_name = serializers.CharField(source="salary_record.imam_name", read_only=True)

    class Meta:
        model = ImamSalaryInstallment
        fields = [
            "id",
            "salary_record",
            "imam_name",
            "payment_date",
            "amount_paid",
            "notes",
            "notes_ur",
        ]


class InstallmentCreateSerializer(serializers.ModelSerializer):
    """
    Mirrors the website's "add payment" form:
      payment_type = "full"        -> pays exactly what is still remaining
      payment_type = "installment" -> pays `amount_paid` (never more than what is remaining)
    """

    salary = serializers.PrimaryKeyRelatedField(
        queryset=ImamSalary.objects.all(), source="salary_record", required=False
    )
    payment_type = serializers.ChoiceField(
        choices=["full", "installment"], required=False, default="installment", write_only=True
    )

    class Meta:
        model = ImamSalaryInstallment
        fields = [
            "id",
            "salary",
            "salary_record",
            "payment_date",
            "amount_paid",
            "payment_type",
            "notes",
            "notes_ur",
        ]
        extra_kwargs = {
            "salary_record": {"required": False},
            "amount_paid": {"required": False},
            "payment_date": {"required": False},
        }

    def validate(self, attrs):
        salary = attrs.get("salary_record")
        if salary is None:
            raise serializers.ValidationError({"salary": "Salary record select karna lazmi hai."})

        remaining = Decimal(str(salary.remaining_salary)).quantize(Decimal("0.01"))
        payment_type = attrs.pop("payment_type", "installment")
        note = (attrs.get("notes") or "").strip()
        note_ur = attrs.get("notes_ur") or ""

        if payment_type == "full":
            amount = remaining
            attrs["notes"] = f"Full Payment ({note})" if note else "Full Payment"
            attrs["notes_ur"] = composed_ur("Full Payment", note, note_ur)
        else:
            amount = attrs.get("amount_paid")
            if amount is None:
                raise serializers.ValidationError({"amount_paid": "Raqam darj karna lazmi hai."})
            attrs["notes"] = f"Qist/Installment ({note})" if note else "Qist Payment"
            attrs["notes_ur"] = composed_ur("Qist/Installment", note, note_ur, "Qist Payment")

        amount = min(Decimal(amount), remaining)
        if amount <= 0:
            raise serializers.ValidationError(
                {"amount_paid": "Valid amount darj karein (ya salary pehle hi mukammal ada ho chuki hai)."}
            )
        attrs["amount_paid"] = amount
        attrs.setdefault("payment_date", timezone.now().date())
        return attrs


class ImamSalarySerializer(UrduApprovalMixin, serializers.ModelSerializer):
    URDU_PAIRS = (("imam_name", "imam_name_ur"),)

    month_year = MonthYearDateField()
    installments = ImamSalaryInstallmentSerializer(many=True, read_only=True)
    effective_yearly_salary = serializers.FloatField(read_only=True)
    total_paid = serializers.FloatField(read_only=True)
    remaining_salary = serializers.FloatField(read_only=True)
    total_paid_year = serializers.FloatField(read_only=True)
    remaining_yearly_salary = serializers.FloatField(read_only=True)
    is_fully_paid = serializers.BooleanField(read_only=True)

    # Optional "record a payment right away" part of the website's add-salary form.
    payment_type = serializers.ChoiceField(
        choices=["none", "full", "installment"], required=False, write_only=True
    )
    payment_date = serializers.DateField(required=False, write_only=True)
    initial_amount_paid = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True, write_only=True
    )
    notes = serializers.CharField(required=False, allow_blank=True, write_only=True)
    notes_ur = serializers.CharField(required=False, allow_blank=True, write_only=True)

    _EXTRA_WRITE_ONLY = ("payment_type", "payment_date", "initial_amount_paid", "notes", "notes_ur")

    class Meta:
        model = ImamSalary
        fields = [
            "id",
            "imam_name",
            "imam_name_ur",
            "month_year",
            "total_salary",
            "yearly_salary",
            "effective_yearly_salary",
            "total_paid",
            "remaining_salary",
            "total_paid_year",
            "remaining_yearly_salary",
            "is_fully_paid",
            "installments",
            "payment_type",
            "payment_date",
            "initial_amount_paid",
            "notes",
            "notes_ur",
        ]
        extra_kwargs = {"yearly_salary": {"required": False}}

    def _normalise_yearly(self, validated_data):
        """Yearly salary falls back to monthly x 10 (same default as the website)."""
        creating = self.instance is None
        if creating or "yearly_salary" in validated_data:
            yearly = validated_data.get("yearly_salary")
            monthly = validated_data.get("total_salary")
            if monthly is None and self.instance is not None:
                monthly = self.instance.total_salary
            if (yearly is None or yearly <= 0) and monthly is not None:
                validated_data["yearly_salary"] = monthly * 10

    @transaction.atomic
    def create(self, validated_data):
        payment_type = validated_data.pop("payment_type", "none")
        payment_date = validated_data.pop("payment_date", None) or timezone.now().date()
        initial = validated_data.pop("initial_amount_paid", None)
        note = (validated_data.pop("notes", "") or "").strip()
        note_ur = validated_data.pop("notes_ur", "") or ""
        self._normalise_yearly(validated_data)

        salary = ImamSalary.objects.create(**validated_data)

        if payment_type == "full":
            ImamSalaryInstallment.objects.create(
                salary_record=salary,
                payment_date=payment_date,
                amount_paid=salary.total_salary,
                notes=f"Full Payment ({note})" if note else "Full Payment",
                notes_ur=composed_ur("Full Payment", note, note_ur),
            )
        elif payment_type == "installment" and initial:
            ImamSalaryInstallment.objects.create(
                salary_record=salary,
                payment_date=payment_date,
                amount_paid=min(initial, salary.total_salary),
                notes=f"Qist/Installment ({note})" if note else "Pehli Qist",
                notes_ur=composed_ur("Qist/Installment", note, note_ur, "Pehli Qist"),
            )
        return salary

    def update(self, instance, validated_data):
        for name in self._EXTRA_WRITE_ONLY:
            validated_data.pop(name, None)
        self._normalise_yearly(validated_data)
        return super().update(instance, validated_data)
