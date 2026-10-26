from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    WeeklyIncome,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    EidCollection,
)


def user_payload(user):
    """Returns standardized user payload for auth endpoints."""
    return {
        "id": user.id,
        "username": user.username,
        "email": getattr(user, "email", "") or "",
        "first_name": getattr(user, "first_name", "") or "",
        "last_name": getattr(user, "last_name", "") or "",
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
    }


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
class WeeklyIncomeSerializer(serializers.ModelSerializer):
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
        ]


class IncomeBatchSerializer(serializers.Serializer):
    items = WeeklyIncomeSerializer(many=True, required=False)

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"items": data}
        return super().to_internal_value(data)

    def create(self, validated_data):
        items_data = validated_data.get("items", [])
        instances = [WeeklyIncome(**item) for item in items_data]
        return WeeklyIncome.objects.bulk_create(instances)


# ==========================================================================
# Expense Serializers
# ==========================================================================
class ExpenseSerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source="get_category_display", read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id",
            "date",
            "description",
            "amount",
            "category",
            "category_display",
        ]


class ExpenseBatchSerializer(serializers.Serializer):
    items = ExpenseSerializer(many=True, required=False)

    def to_internal_value(self, data):
        if isinstance(data, list):
            data = {"items": data}
        return super().to_internal_value(data)

    def create(self, validated_data):
        items_data = validated_data.get("items", [])
        instances = [Expense(**item) for item in items_data]
        return Expense.objects.bulk_create(instances)


# ==========================================================================
# Eid Collection Serializer
# ==========================================================================
class EidCollectionSerializer(serializers.ModelSerializer):
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
            "imam_type",
            "imam_type_display",
            "amount_collected",
            "notes",
        ]


# ==========================================================================
# Land Lease Serializers
# ==========================================================================
class LandLeasePaymentSerializer(serializers.ModelSerializer):
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
        ]


class LandLeaseSerializer(serializers.ModelSerializer):
    payments = LandLeasePaymentSerializer(many=True, read_only=True)
    total_received = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    remaining_lease_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = LandLease
        fields = [
            "id",
            "land_area",
            "tenant_name",
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
class ImamSalaryInstallmentSerializer(serializers.ModelSerializer):
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
        ]


class InstallmentCreateSerializer(serializers.ModelSerializer):
    salary = serializers.PrimaryKeyRelatedField(
        queryset=ImamSalary.objects.all(), source="salary_record", required=False
    )

    class Meta:
        model = ImamSalaryInstallment
        fields = [
            "id",
            "salary",
            "salary_record",
            "payment_date",
            "amount_paid",
            "notes",
        ]
        extra_kwargs = {
            "salary_record": {"required": False}
        }

    def validate(self, attrs):
        if "salary_record" not in attrs:
            raise serializers.ValidationError({"salary": "Salary record select karna lazmi hai."})
        return attrs


class ImamSalarySerializer(serializers.ModelSerializer):
    installments = ImamSalaryInstallmentSerializer(many=True, read_only=True)
    effective_yearly_salary = serializers.FloatField(read_only=True)
    total_paid = serializers.FloatField(read_only=True)
    remaining_salary = serializers.FloatField(read_only=True)
    total_paid_year = serializers.FloatField(read_only=True)
    remaining_yearly_salary = serializers.FloatField(read_only=True)
    is_fully_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = ImamSalary
        fields = [
            "id",
            "imam_name",
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
        ]
