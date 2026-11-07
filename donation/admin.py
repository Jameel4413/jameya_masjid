from django.contrib import admin
from .models import (
    WeeklyIncome,
    Expense,
    ImamSalary,
    ImamSalaryInstallment,
    LandLease,
    LandLeasePayment,
    EidCollection,
    WordMapping,
)
# Register your models here.
# Admin Site Title & Header Customize
admin.site.site_header = "Masjid Financial Management System"
admin.site.site_title = "Masjid Admin"
admin.site.index_title = "Hisab-Kitab Dashboard"


# 1. Weekly Income Admin
@admin.register(WeeklyIncome)
class WeeklyIncomeAdmin(admin.ModelAdmin):
    list_display = ('date', 'day_type', 'amount', 'notes')
    list_filter = ('day_type', 'date')
    search_fields = ('notes',)
    date_hierarchy = 'date'


# 2. Expense Admin
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('description', 'amount', 'category', 'date')
    list_filter = ('category', 'date')
    search_fields = ('description',)
    date_hierarchy = 'date'


# 3. Imam Salary & Inline Installments Admin
class ImamSalaryInstallmentInline(admin.TabularInline):
    model = ImamSalaryInstallment
    extra = 1
    fields = ('payment_date', 'amount_paid', 'notes', 'notes_ur')


@admin.register(ImamSalary)
class ImamSalaryAdmin(admin.ModelAdmin):
    list_display = ('imam_name', 'get_month_year', 'total_salary', 'get_total_paid', 'get_remaining_salary', 'is_fully_paid')
    inlines = [ImamSalaryInstallmentInline]
    date_hierarchy = 'month_year'

    def get_month_year(self, obj):
        return obj.month_year.strftime('%B %Y')
    get_month_year.short_description = "Month/Year"

    def get_total_paid(self, obj):
        return f"RS {obj.total_paid:,.2f}"
    get_total_paid.short_description = "Paid So Far"

    def get_remaining_salary(self, obj):
        return f"RS {obj.remaining_salary:,.2f}"
    get_remaining_salary.short_description = "Remaining Unpaid"


# 4. Land Lease & Inline Payments Admin
class LandLeasePaymentInline(admin.TabularInline):
    model = LandLeasePayment
    extra = 1
    fields = ('payment_date', 'amount_received', 'notes', 'notes_ur')


@admin.register(LandLease)
class LandLeaseAdmin(admin.ModelAdmin):
    list_display = ('tenant_name', 'land_area', 'total_agreed_amount', 'get_total_received', 'get_remaining_lease', 'duration_years')
    inlines = [LandLeasePaymentInline]

    def get_total_received(self, obj):
        return f"RS {obj.total_received:,.2f}"
    get_total_received.short_description = "Total Received"

    def get_remaining_lease(self, obj):
        return f"RS {obj.remaining_lease_amount:,.2f}"
    get_remaining_lease.short_description = "Remaining Balance"


# 5. Special Eid Collection Admin
@admin.register(EidCollection)
class EidCollectionAdmin(admin.ModelAdmin):
    list_display = ('eid_name', 'imam_name', 'imam_type', 'amount_collected', 'date')
    list_filter = ('eid_name', 'imam_type', 'date')
    search_fields = ('imam_name',)


# 8. Word Mapping (Roman Urdu -> Urdu words learnt from corrections in the forms)
@admin.register(WordMapping)
class WordMappingAdmin(admin.ModelAdmin):
    list_display = ('roman', 'urdu', 'updated_at')
    search_fields = ('roman', 'urdu')
    ordering = ('roman',)
    list_per_page = 100

    def _refresh_cache(self):
        from .urdu_input import _invalidate
        _invalidate()          # forms / PDFs pick up the change immediately

    def save_model(self, request, obj, form, change):
        obj.roman = (obj.roman or '').strip().lower()
        obj.urdu = (obj.urdu or '').strip()
        super().save_model(request, obj, form, change)
        self._refresh_cache()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._refresh_cache()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        self._refresh_cache()