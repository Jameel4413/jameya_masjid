import io
import os
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from django.contrib import messages

def logout_view(request):
    logout(request)
    return redirect('admin:login')

@login_required
def change_password_view(request):
    if request.method == 'POST':
        old_password = request.POST.get('old_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        if not request.user.check_password(old_password):
            messages.error(request, 'Purana password sahi nahi hai! (Incorrect old password)')
        elif new_password != confirm_password:
            messages.error(request, 'Naya password dono jagah match nahi ho raha! (Passwords do not match)')
        elif len(new_password) < 6:
            messages.error(request, 'Naya password kam az kam 6 aksar (characters) ka hona chahiye!')
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password kamyabi se badal diya gaya hai! (Password updated successfully)')

    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))



from django.conf import settings
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .models import (
    WeeklyIncome,
    Expense,
    ImamSalaryInstallment,
    LandLeasePayment,
    EidCollection,
    LandLease,
    ImamSalary
)
from .translations import translate_user_input_to_urdu

_URDU_FONT_REGISTERED = False

URDU_MONTH_NAMES = {
    1: 'جنوری', 2: 'فروری', 3: 'مارچ', 4: 'اپریل',
    5: 'مئی', 6: 'جون', 7: 'جولائی', 8: 'اگست',
    9: 'ستمبر', 10: 'اکتوبر', 11: 'نومبر', 12: 'دسمبر'
}

EXPENSE_CAT_URDU = {
    'Electricity / Water Bills': 'بجلی / پانی کے بل',
    'UTILITIES': 'بجلی / پانی کے بل',
    'Utilities': 'بجلی / پانی کے بل',
    'Repairing & Maintenance': 'مرمت و دیکھ بھال',
    'REPAIR': 'مرمت و دیکھ بھال',
    'Repairing': 'مرمت و دیکھ بھال',
    'Cleaning & Supplies': 'صفائی اور سامان',
    'CLEANING': 'صفائی اور سامان',
    'Cleaning': 'صفائی اور سامان',
    'Event / Program Expense': 'پروگرام / تقریب',
    'EVENT': 'پروگرام / تقریب',
    'Event / Program': 'پروگرام / تقریب',
    'Event': 'پروگرام / تقریب',
    'Other Expense': 'دیگر اخراجات',
    'OTHER': 'دیگر اخراجات',
    'Other Expenses': 'دیگر اخراجات',
    'Other': 'دیگر اخراجات',
    'Imam Salary': 'امام کی تنخواہ',
    'Imam Salary Record': 'امام کی تنخواہ کا ریکارڈ',
}

DAY_TYPE_URDU = {
    'Friday Collection': 'جمعہ کا چندہ',
    'FRIDAY': 'جمعہ کا چندہ',
    'Thursday Collection': 'جمعرات کا چندہ',
    'THURSDAY': 'جمعرات کا چندہ',
    'Other Collection': 'دیگر چندہ',
    'OTHER': 'دیگر چندہ',
    'Friday': 'جمعہ کا چندہ',
    'juma': 'جمعہ کا چندہ',
    'Thursday': 'جمعرات کا چندہ',
    'Other': 'دیگر چندہ',
}

import re


def register_urdu_fonts():
    global _URDU_FONT_REGISTERED
    if not _URDU_FONT_REGISTERED:
        local_font_dir = os.path.join(settings.BASE_DIR, 'donation', 'fonts')
        local_reg = os.path.join(local_font_dir, 'tahoma.ttf')
        local_bold = os.path.join(local_font_dir, 'tahomabd.ttf')

        font_paths = [
            # 1. Bundled High-Precision Book Fonts (Fully compatible with ReportLab shaping)
            (local_reg, local_bold),
            # 2. Windows System Fonts
            ("C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/tahomabd.ttf"),
            ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
            ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
            # 3. Linux / Vercel Serverless System Fonts
            ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
        ]
        for regular, bold in font_paths:
            if os.path.exists(regular) and os.path.exists(bold):
                try:
                    pdfmetrics.registerFont(TTFont('UrduNaskh', regular))
                    pdfmetrics.registerFont(TTFont('UrduNaskh-Bold', bold))
                    pdfmetrics.registerFont(TTFont('UrduFont', regular))
                    pdfmetrics.registerFont(TTFont('UrduFont-Bold', bold))
                    pdfmetrics.registerFont(TTFont('UrduNastaliq', bold))
                    _URDU_FONT_REGISTERED = True
                    break
                except Exception:
                    pass

        _URDU_FONT_REGISTERED = True

_ARABIC_RESHAPER_PRESERVE_HARAKAT = arabic_reshaper.ArabicReshaper({
    'delete_harakat': False,
    'support_ligatures': True,
    'delete_tatweel': False,
})

def shape_ur(text, is_urdu=False):
    if text is None:
        return ""
    str_text = str(text)
    if not is_urdu or not str_text.strip():
        return str_text
    
    str_text = translate_user_input_to_urdu(str_text)
    register_urdu_fonts()
    reshaped = _ARABIC_RESHAPER_PRESERVE_HARAKAT.reshape(str_text)
    return get_display(reshaped)

def set_language(request):
    lang = request.GET.get('lang', 'en')
    if lang in ['en', 'ur']:
        request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# Helper function to apply Month/Year filters dynamically across views
def filter_by_month_year(queryset, date_field, request):
    year = request.GET.get('year')
    month = request.GET.get('month')
    filter_kwargs = {}
    if year:
        filter_kwargs[f'{date_field}__year'] = year
    if month:
        filter_kwargs[f'{date_field}__month'] = month
    return queryset.filter(**filter_kwargs)


def get_all_time_totals():
    """
    Calculates the TRUE running balance since the system started.
    This NEVER resets on a weekly/monthly basis - it is the sum of
    everything that has ever come in, minus everything that has ever
    gone out. This fixes the bug where the dashboard balance was being
    reset every week and old expenses appeared to "cut" from new income.
    """
    total_weekly_income = WeeklyIncome.objects.aggregate(t=Sum('amount'))['t'] or 0
    total_lease_income = LandLeasePayment.objects.aggregate(t=Sum('amount_received'))['t'] or 0
    grand_total_income = total_weekly_income + total_lease_income

    total_expenses = Expense.objects.aggregate(t=Sum('amount'))['t'] or 0
    total_salary_paid = ImamSalaryInstallment.objects.aggregate(t=Sum('amount_paid'))['t'] or 0
    grand_total_expense = total_expenses + total_salary_paid

    return grand_total_income, grand_total_expense


# ==========================================
# 1. MAIN DASHBOARD VIEW
# ==========================================
@login_required(login_url='/admin/login/')
def dashboard_view(request):
    now = timezone.now()

    # ---- ALL-TIME RUNNING BALANCE (the real "cash in hand") ----
    grand_total_income_all, grand_total_expense_all = get_all_time_totals()
    total_balance_in_hand = grand_total_income_all - grand_total_expense_all

    # ---- SELECTED PERIOD SNAPSHOT (defaults to current month, for the filter box) ----
    year = request.GET.get('year')
    month = request.GET.get('month')

    curr_year = int(year) if (year and year.isdigit()) else now.year
    curr_month = int(month) if (month and month.isdigit()) else now.month

    weekly_qs = WeeklyIncome.objects.filter(date__year=curr_year, date__month=curr_month)
    lease_qs = LandLeasePayment.objects.filter(payment_date__year=curr_year, payment_date__month=curr_month)
    expense_qs = Expense.objects.filter(date__year=curr_year, date__month=curr_month)
    salary_qs = ImamSalaryInstallment.objects.filter(payment_date__year=curr_year, payment_date__month=curr_month)

    period_income = (weekly_qs.aggregate(t=Sum('amount'))['t'] or 0) + \
                     (lease_qs.aggregate(t=Sum('amount_received'))['t'] or 0)
    period_expense = (expense_qs.aggregate(t=Sum('amount'))['t'] or 0) + \
                      (salary_qs.aggregate(t=Sum('amount_paid'))['t'] or 0)
    period_net = period_income - period_expense

    recent_incomes = WeeklyIncome.objects.all().order_by('-date')[:5]
    recent_expenses = Expense.objects.all().order_by('-date')[:5]

    context = {
        'total_balance_in_hand': total_balance_in_hand,
        'grand_total_income': period_income,
        'grand_total_expense': period_expense,
        'period_net': period_net,
        'recent_incomes': recent_incomes,
        'recent_expenses': recent_expenses,
        'selected_year': request.GET.get('year', str(curr_year)),
        'selected_month': request.GET.get('month', str(curr_month)),
        'period_label': datetime(curr_year, curr_month, 1).strftime('%B %Y'),
    }

    return render(request, 'dashboard.html', context)


# ==========================================
# 2. INDIVIDUAL SECTIONS WITH FILTERS
# ==========================================

@login_required(login_url='/admin/login/')
def weekly_income_view(request):
    """Thursday & Friday Collections View with Month/Year Filter"""
    incomes = WeeklyIncome.objects.all().order_by('-date')
    incomes = filter_by_month_year(incomes, 'date', request)

    total_collected = incomes.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'incomes': incomes,
        'total_collected': total_collected,
        'selected_year': request.GET.get('year', ''),
        'selected_month': request.GET.get('month', ''),
    }
    return render(request, 'weekly_income.html', context)


@login_required(login_url='/admin/login/')
def expenses_view(request):
    """Masjid Kharajaat View with Month/Year Filter"""
    expenses = Expense.objects.all().order_by('-date')
    expenses = filter_by_month_year(expenses, 'date', request)

    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'expenses': expenses,
        'total_expenses': total_expenses,
        'selected_year': request.GET.get('year', ''),
        'selected_month': request.GET.get('month', ''),
    }
    return render(request, 'expenses.html', context)


@login_required(login_url='/admin/login/')
def land_lease_view(request):
    """Land Lease with Full/Installment Payments Tracking & Filters"""
    leases = LandLease.objects.all().order_by('-start_date')
    leases = filter_by_month_year(leases, 'start_date', request)

    total_pending_lease_amount = sum(lease.remaining_lease_amount for lease in leases)

    context = {
        'leases': leases,
        'total_pending_lease_amount': total_pending_lease_amount,
        'selected_year': request.GET.get('year', ''),
        'selected_month': request.GET.get('month', ''),
    }
    return render(request, 'land_lease.html', context)


# ==========================================
# 3. IMAM SALARY - CORE LOGIC (FIXED)
# ==========================================

@login_required(login_url='/admin/login/')
def imam_salary_view(request):
    """
    Defaults to the CURRENT month & year on first load.
    Shows per-month totals AND per-year totals side by side.
    """
    now = timezone.now()
    year = request.GET.get('year')
    month = request.GET.get('month')

    is_default_view = not year and not month

    curr_year = int(year) if (year and year.isdigit()) else now.year
    curr_month = int(month) if (month and month.isdigit()) else now.month

    # Month-wise list (defaults to current month so the current status is
    # always visible without the user having to filter manually)
    salaries = ImamSalary.objects.filter(month_year__year=curr_year)
    if is_default_view or month:
        salaries = salaries.filter(month_year__month=curr_month)
    salaries = salaries.order_by('-month_year')

    total_month_salary_value = sum(s.total_salary for s in salaries)
    total_month_paid = sum(s.total_paid for s in salaries)
    total_month_remaining = sum(s.remaining_salary for s in salaries)

    # Year-wise totals (independent of month filter)
    year_salaries = ImamSalary.objects.filter(month_year__year=curr_year)
    distinct_imams = set(year_salaries.values_list('imam_name', flat=True))
    total_year_salary_value = 0.0
    for imam in distinct_imams:
        imam_latest = year_salaries.filter(imam_name=imam).order_by('-month_year').first()
        if imam_latest:
            total_year_salary_value += imam_latest.effective_yearly_salary

    total_year_paid = sum(s.total_paid for s in year_salaries)
    total_year_remaining = max(0.0, total_year_salary_value - total_year_paid)

    context = {
        'salaries': salaries,
        'total_pending_salary_amount': total_month_remaining,
        'total_month_salary_value': total_month_salary_value,
        'total_month_paid': total_month_paid,
        'total_month_remaining': total_month_remaining,
        'total_year_salary_value': total_year_salary_value,
        'total_year_paid': total_year_paid,
        'total_year_remaining': total_year_remaining,
        'selected_year': str(curr_year),
        'selected_month': str(curr_month) if (is_default_view or month) else '',
        'current_period_label': datetime(curr_year, curr_month, 1).strftime('%B %Y'),
        'is_default_view': is_default_view,
    }
    return render(request, 'imam_salary.html', context)


@login_required(login_url='/admin/login/')
def add_imam_salary_view(request):
    if request.method == 'POST':
        imam_name = request.POST.get('imam_name')
        month_year = request.POST.get('month_year')
        total_salary = request.POST.get('total_salary')
        yearly_sal_raw = request.POST.get('yearly_salary')
        payment_type = request.POST.get('payment_type')
        payment_date = request.POST.get('payment_date')
        initial_amount_paid = request.POST.get('initial_amount_paid')
        notes = request.POST.get('notes', '')

        if imam_name and month_year and total_salary:
            date_obj = datetime.strptime(month_year, '%Y-%m').date()
            tot_sal_float = float(total_salary)
            if yearly_sal_raw and float(yearly_sal_raw) > 0:
                yearly_sal_val = float(yearly_sal_raw)
            else:
                yearly_sal_val = tot_sal_float * 10

            salary_obj = ImamSalary.objects.create(
                imam_name=imam_name,
                month_year=date_obj,
                total_salary=tot_sal_float,
                yearly_salary=yearly_sal_val
            )

            # If the user chose to record a payment right away (full or first installment)
            if payment_type == 'full':
                ImamSalaryInstallment.objects.create(
                    salary_record=salary_obj,
                    payment_date=payment_date or timezone.now().date(),
                    amount_paid=tot_sal_float,
                    notes=f"Full Payment ({notes})" if notes else "Full Payment"
                )
            elif payment_type == 'installment' and initial_amount_paid:
                ImamSalaryInstallment.objects.create(
                    salary_record=salary_obj,
                    payment_date=payment_date or timezone.now().date(),
                    amount_paid=float(initial_amount_paid),
                    notes=f"Qist/Installment ({notes})" if notes else "Pehli Qist"
                )

            messages.success(request, "Imam ki monthly salary record add ho gayi.")
        else:
            messages.error(request, "Tamam zaroori fields pur karein.")

    return redirect('imam_salary')


@login_required(login_url='/admin/login/')
def add_imam_installment_view(request):
    """Add payment: Form includes Dropdown for payment mode (Full vs Installment)"""
    if request.method == 'POST':
        salary_id = request.POST.get('salary_id')
        payment_type = request.POST.get('payment_type')  # 'full' or 'installment'
        payment_date = request.POST.get('payment_date')
        amount_paid = request.POST.get('amount_paid')
        notes = request.POST.get('notes', '')

        salary_obj = get_object_or_404(ImamSalary, id=salary_id)

        if payment_type == 'full':
            amount_to_pay = float(salary_obj.remaining_salary)
            notes_detail = f"Full Payment ({notes})" if notes else "Full Payment"
        else:
            amount_to_pay = float(amount_paid) if amount_paid else 0.0
            notes_detail = f"Qist/Installment ({notes})" if notes else "Qist Payment"

        # Never allow overpaying beyond what's actually remaining
        amount_to_pay = min(amount_to_pay, float(salary_obj.remaining_salary))

        if amount_to_pay > 0:
            ImamSalaryInstallment.objects.create(
                salary_record=salary_obj,
                payment_date=payment_date,
                amount_paid=amount_to_pay,
                notes=notes_detail
            )
            messages.success(request, "Salary payment record ho gayi.")
        else:
            messages.error(request, "Valid amount darj karein (ya salary pehle hi mukammal ada ho chuki hai).")

    return redirect('imam_salary')


@login_required(login_url='/admin/login/')
def update_imam_installment_view(request, pk):
    """Payment / Installment record ko Update/Edit karne ke liye"""
    installment = get_object_or_404(ImamSalaryInstallment, pk=pk)
    if request.method == 'POST':
        installment.payment_date = request.POST.get('payment_date')
        installment.amount_paid = float(request.POST.get('amount_paid'))
        installment.notes = request.POST.get('notes')
        installment.save()
        messages.success(request, "Payment detail update ho gayi!")
    return redirect('imam_salary')


@login_required(login_url='/admin/login/')
def delete_imam_installment_view(request, pk):
    """Payment / Installment entry ko Delete karne ke liye"""
    installment = get_object_or_404(ImamSalaryInstallment, pk=pk)
    if request.method == 'POST':
        installment.delete()
        messages.success(request, "Payment entry delete ho gayi.")
    return redirect('imam_salary')


@login_required(login_url='/admin/login/')
def update_imam_salary_view(request, pk):
    salary = get_object_or_404(ImamSalary, pk=pk)
    if request.method == 'POST':
        salary.imam_name = request.POST.get('imam_name')
        tot_sal = float(request.POST.get('total_salary'))
        salary.total_salary = tot_sal
        yearly_sal_raw = request.POST.get('yearly_salary')
        if yearly_sal_raw and float(yearly_sal_raw) > 0:
            salary.yearly_salary = float(yearly_sal_raw)
        else:
            salary.yearly_salary = tot_sal * 10
        month_year_str = request.POST.get('month_year')
        if month_year_str:
            salary.month_year = datetime.strptime(month_year_str, '%Y-%m').date()
        salary.save()
        messages.success(request, "Imam salary header record update ho gaya!")
    return redirect('imam_salary')


@login_required(login_url='/admin/login/')
def delete_imam_salary_view(request, pk):
    salary = get_object_or_404(ImamSalary, pk=pk)
    if request.method == 'POST':
        salary.delete()
        messages.success(request, "Mukammal Salary Record delete ho gaya.")
    return redirect('imam_salary')


def draw_islamic_pdf_background(canvas, doc):
    """
    Renders an Executive Islamic Theme background with 0% DB overhead:
    - Rich Soft Islamic Sage Canvas Tint (#e1f0e6)
    - Bold Double Golden Frame (#c59b27 Rich Metallic Gold & #044e3a Emerald)
    - Four Corner Geometric Architectural Diamonds in Gold & Emerald
    - Subtle Center Watermark
    - Executive Footer line
    """
    canvas.saveState()
    width, height = doc.pagesize

    # 1. Canvas Fill: Rich Soft Islamic Sage Tint (#e1f0e6)
    canvas.setFillColor(colors.HexColor('#e1f0e6'))
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer Bold Golden Frame (#c59b27 - Rich Gold)
    margin = 18
    canvas.setStrokeColor(colors.HexColor('#c59b27'))
    canvas.setLineWidth(3.0)
    canvas.rect(margin, margin, width - (2 * margin), height - (2 * margin))

    # Inner Emerald Accent Line (#044e3a)
    canvas.setStrokeColor(colors.HexColor('#044e3a'))
    canvas.setLineWidth(1.2)
    canvas.rect(margin + 4, margin + 4, width - (2 * margin) - 8, height - (2 * margin) - 8)

    # Corner Geometric Diamond Ornaments (Golden & Emerald)
    canvas.setStrokeColor(colors.HexColor('#c59b27'))
    canvas.setFillColor(colors.HexColor('#044e3a')) # Deep Emerald
    canvas.setLineWidth(1.2)
    c_off = margin + 4

    corners = [
        (c_off, height - c_off),        # Top-Left
        (width - c_off, height - c_off), # Top-Right
        (c_off, c_off),                 # Bottom-Left
        (width - c_off, c_off)          # Bottom-Right
    ]
    for x_c, y_c in corners:
        p = canvas.beginPath()
        p.moveTo(x_c - 9, y_c)
        p.lineTo(x_c, y_c + 9)
        p.lineTo(x_c + 9, y_c)
        p.lineTo(x_c, y_c - 9)
        p.close()
        canvas.drawPath(p, fill=1, stroke=1)

    # 3. Subtle Center Watermark
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#044e3a'))
    canvas.setFillAlpha(0.04)
    canvas.setFont('Helvetica-Bold', 36)
    canvas.drawCentredString(width / 2.0, height / 2.0 + 10, "JAMEYA MASJID")
    canvas.setFont('Helvetica-Bold', 15)
    canvas.drawCentredString(width / 2.0, height / 2.0 - 25, "FINANCIAL MANAGEMENT SYSTEM")
    canvas.restoreState()

    # 4. Executive Footer Line
    footer_y = 26
    canvas.setStrokeColor(colors.HexColor('#c59b27'))
    canvas.setLineWidth(1.2)
    canvas.line(margin + 6, footer_y + 8, width - margin - 6, footer_y + 8)

    canvas.setFillColor(colors.HexColor('#044e3a'))
    canvas.setFont('Helvetica-Bold', 8)
    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    canvas.drawString(margin + 10, footer_y - 4, f"Generated: {now_str}")
    canvas.drawRightString(width - margin - 10, footer_y - 4, f"Page {doc.page}  |  JAMEYA MASJID OFFICIAL RECORD")

    canvas.restoreState()


@login_required(login_url='/admin/login/')
def export_imam_salary_pdf(request):
    """Dedicated PDF - ONLY the Imam Salary status (per-month + year total). Supports English and Urdu."""
    register_urdu_fonts()
    registered_fonts = pdfmetrics.getRegisteredFontNames()

    year = request.GET.get('year')
    month = request.GET.get('month')
    pdf_lang = request.GET.get('lang') or request.GET.get('pdf_lang') or (request.session.get('lang', 'en') if hasattr(request, 'session') and request.session is not None else 'en')
    is_urdu = (pdf_lang == 'ur')

    font_normal = 'UrduFont' if (is_urdu and 'UrduFont' in registered_fonts) else 'Helvetica'
    font_bold = 'UrduFont-Bold' if (is_urdu and 'UrduFont-Bold' in registered_fonts) else 'Helvetica-Bold'
    font_bism = 'UrduFont-Bold' if ('UrduFont-Bold' in registered_fonts) else font_bold

    now = timezone.now()
    selected_year = int(year) if (year and year.isdigit()) else now.year
    
    selected_month = None
    is_annual = True
    if month and month != 'all':
        if month.isdigit():
            selected_month = int(month)
            is_annual = False

    salaries = ImamSalary.objects.filter(month_year__year=selected_year)
    if not is_annual:
        salaries = salaries.filter(month_year__month=selected_month)
    salaries = salaries.order_by('month_year')

    # Compute totals
    total_month_budgeted = sum(s.total_salary for s in salaries)
    distinct_imams_pdf = set(salaries.values_list('imam_name', flat=True))
    total_year_budgeted = 0.0
    for imam in distinct_imams_pdf:
        imam_latest = salaries.filter(imam_name=imam).order_by('-month_year').first()
        if imam_latest:
            total_year_budgeted += imam_latest.effective_yearly_salary

    total_paid = sum(s.total_paid for s in salaries)
    total_month_remaining = sum(s.remaining_salary for s in salaries)
    total_year_remaining = max(0.0, total_year_budgeted - total_paid)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Authentic Islamic Crest Banner for Bismillah with exact Arabic diacritics & side titles
    bismillah_exact_text = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
    bismillah_str = shape_ur(bismillah_exact_text, is_urdu=True)
    allah_str = shape_ur("یا اللہ", is_urdu=True)
    rasool_str = shape_ur("یا رسول اللہ", is_urdu=True)

    bism_center_style = ParagraphStyle(
        'BismCenterS', parent=styles['Normal'], fontName=font_bism, fontSize=21.5, leading=26,
        textColor=colors.HexColor("#fef08a"), alignment=1
    )
    bism_right_style = ParagraphStyle(
        'BismRightS', parent=styles['Normal'], fontName=font_bism, fontSize=14, leading=18,
        textColor=colors.HexColor("#fef08a"), alignment=2
    )
    bism_left_style = ParagraphStyle(
        'BismLeftS', parent=styles['Normal'], fontName=font_bism, fontSize=14, leading=18,
        textColor=colors.HexColor("#fef08a"), alignment=0
    )

    p_left = Paragraph(f"<b>{rasool_str}</b>", bism_left_style)
    p_center = Paragraph(f"<b>{bismillah_str}</b>", bism_center_style)
    p_right = Paragraph(f"<b>{allah_str}</b>", bism_right_style)

    bism_box = Table([[p_left, p_center, p_right]], colWidths=[120, 280, 120])
    bism_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#044e3a")), # Deep Sacred Emerald Fill
        ('BOX', (0, 0), (-1, -1), 2.5, colors.HexColor("#c59b27")), # Outer Metallic Gold Frame
        ('LINEABOVE', (0, 0), (-1, -1), 1.2, colors.HexColor("#fef08a")), # Inner Gold Line Accent
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor("#fef08a")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(bism_box)
    story.append(Spacer(1, 14))

    # High contrast sharp text styles (Increased font sizes & bold weights for ultra-readable printouts)
    title_style = ParagraphStyle(
        'RepTitle', parent=styles['Heading1'], fontName=font_bold, fontSize=19 if is_urdu else 22, leading=25,
        textColor=colors.HexColor("#044e3a"), alignment=1
    )
    subtitle_style = ParagraphStyle(
        'RepSubtitle', parent=styles['Normal'], fontName=font_bold, fontSize=12.5, leading=16,
        textColor=colors.HexColor("#000000"), alignment=1
    )
    section_style = ParagraphStyle(
        'RepSection', parent=styles['Heading2'], fontName=font_bold, fontSize=15.5, leading=20,
        textColor=colors.HexColor("#044e3a"), spaceBefore=18, spaceAfter=9
    )
    cell_style = ParagraphStyle(
        'RepCell', parent=styles['Normal'], fontName=font_bold, fontSize=11, leading=15,
        textColor=colors.HexColor("#000000") # Pure solid black bold for maximum print clarity
    )
    cell_hdr_style = ParagraphStyle(
        'RepCellHdr', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15,
        textColor=colors.white
    )
    cell_amount_style = ParagraphStyle(
        'RepCellAmt', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15,
        textColor=colors.HexColor("#044e3a"), alignment=2
    )

    # Custom styles for Imam Cards
    imam_name_style = ParagraphStyle(
        'ImamName', parent=styles['Normal'], fontName=font_bold, fontSize=13.5, leading=17,
        textColor=colors.white
    )
    card_info_style = ParagraphStyle(
        'CardInfo', parent=styles['Normal'], fontName=font_bold, fontSize=10, leading=14,
        textColor=colors.HexColor("#0f172a")
    )
    card_footer_style = ParagraphStyle(
        'CardF', parent=styles['Normal'], fontName=font_bold, fontSize=10, leading=15,
        textColor=colors.HexColor("#0f172a")
    )

    # Document Header
    main_title = "جامع مسجد امام کی تنخواہ رپورٹ" if is_urdu else "JAMEYA MASJID IMAM SALARY REPORT"
    story.append(Paragraph(f"<b>{shape_ur(main_title, is_urdu)}</b>", title_style))

    if is_annual:
        period_text = f"سالانہ رپورٹ - سال {selected_year}" if is_urdu else f"Annual Report - Year {selected_year}"
    else:
        m_name = URDU_MONTH_NAMES.get(selected_month, '') if is_urdu else datetime(selected_year, selected_month, 1).strftime('%B')
        m_full = f"{m_name} {selected_year}"
        period_text = f"تفصیلی اسٹیٹمنٹ برائے {m_full}" if is_urdu else f"Detailed Statement for {m_full}"
    story.append(Paragraph(shape_ur(period_text, is_urdu), subtitle_style))
    story.append(Spacer(1, 15))

    # Summary Cards Table
    card_title_style = ParagraphStyle(
        'CardT', parent=styles['Normal'], fontName=font_bold, fontSize=11, leading=14,
        textColor=colors.white, alignment=1
    )
    card_val_inc = ParagraphStyle(
        'CardValInc', parent=styles['Normal'], fontName=font_bold, fontSize=14, leading=18,
        textColor=colors.HexColor("#fef08a"), alignment=1
    )
    card_val_paid = ParagraphStyle(
        'CardValPaid', parent=styles['Normal'], fontName=font_bold, fontSize=14, leading=18,
        textColor=colors.HexColor("#e0f2fe"), alignment=1
    )
    card_val_rem = ParagraphStyle(
        'CardValRem', parent=styles['Normal'], fontName=font_bold, fontSize=14, leading=18,
        textColor=colors.HexColor("#fee2e2"), alignment=1
    )

    lbl_month_tot = "ماہانہ تنخواہ (کل / بقایا)" if is_urdu else "MONTH SALARY (TOTAL / REM)"
    lbl_year_tot = "سالانہ تنخواہ (کل / بقایا)" if is_urdu else "YEAR SALARY (TOTAL / REM)"
    lbl_paid = "کل ادا شدہ" if is_urdu else "TOTAL PAID"

    summary_data = [
        [
            Paragraph(shape_ur(lbl_month_tot, is_urdu), card_title_style),
            Paragraph(shape_ur(lbl_year_tot, is_urdu), card_title_style),
            Paragraph(shape_ur(lbl_paid, is_urdu), card_title_style)
        ],
        [
            Paragraph(f"RS {total_month_budgeted:,.0f} <font color='#fee2e2'>({total_month_remaining:,.0f})</font>", card_val_inc),
            Paragraph(f"RS {total_year_budgeted:,.0f} <font color='#fee2e2'>({total_year_remaining:,.0f})</font>", card_val_rem),
            Paragraph(f"RS {total_paid:,.0f}", card_val_paid)
        ]
    ]

    summary_table = Table(summary_data, colWidths=[180, 180, 180])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#044e3a")), # Sacred Emerald Fill
        ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#991b1b")), # Dark Crimson Fill
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#0369a1")), # Sapphire Blue Fill
        ('BOX', (0, 0), (0, -1), 2.2, colors.HexColor("#c59b27")), # Gold Frame
        ('BOX', (1, 0), (1, -1), 1.8, colors.HexColor("#b71c1c")),
        ('BOX', (2, 0), (2, -1), 1.8, colors.HexColor("#0284c7")),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#fef08a")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))

    # Detailed Cards Section
    section_lbl = "تنخواہ کی تفصیلی معلومات" if is_urdu else "Detailed Salary Records"
    story.append(Paragraph(f"<b>{shape_ur(section_lbl, is_urdu)}</b>", section_style))
    if not salaries.exists():
        no_rec = "اس عرصے کے لیے کوئی تنخواہ کا ریکارڈ موجود نہیں ہے۔" if is_urdu else "No Imam salary records found for this period."
        story.append(Paragraph(shape_ur(no_rec, is_urdu), cell_style))
        story.append(Spacer(1, 15))
    else:
        for s in salaries:
            if is_urdu:
                status_text = "مکمل ادا شدہ" if s.is_fully_paid else "بقایا"
            else:
                status_text = "FULLY PAID" if s.is_fully_paid else "PENDING"
            status_color = "#a7f3d0" if s.is_fully_paid else "#fecaca"
            status_badge_style = ParagraphStyle(
                'ImamStatus', parent=styles['Normal'], fontName=font_bold, fontSize=10, leading=12,
                textColor=colors.HexColor(status_color), alignment=2
            )

            st_prefix = "حالت: " if is_urdu else "STATUS: "
            
            s_month_name = URDU_MONTH_NAMES.get(s.month_year.month, '') if is_urdu else s.month_year.strftime('%B')
            s_period_str = f"{s_month_name} {s.month_year.year}"
            period_label_text = f"مدت تنخواہ: {s_period_str}" if is_urdu else f"Salary Period: {s_period_str}"

            col1 = "ادائیگی کی تاریخ" if is_urdu else "Payment Date"
            col2 = "ادا شدہ رقم" if is_urdu else "Amount Paid"
            col3 = "تفصیل / اقساط" if is_urdu else "Notes / Details"

            salary_card_data = [
                # Row 0: Imam Name & Status Badge
                [
                    Paragraph(f"<b>{shape_ur(s.imam_name, is_urdu)}</b>", imam_name_style),
                    "",
                    Paragraph(f"<b>{shape_ur(st_prefix + status_text, is_urdu)}</b>", status_badge_style)
                ],
                # Row 1: Subtitle details
                [
                    Paragraph(shape_ur(period_label_text, is_urdu), card_info_style),
                    "",
                    ""
                ],
                # Row 2: Table Header
                [
                    Paragraph(f"<b>{shape_ur(col1, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col2, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col3, is_urdu)}</b>", cell_hdr_style)
                ]
            ]
            
            for p in s.installments.all().order_by('payment_date'):
                note_str = p.notes or ("قسط ادائیگی" if is_urdu else "Installment Payment")
                salary_card_data.append([
                    Paragraph(p.payment_date.strftime('%d-%b-%Y'), cell_style),
                    Paragraph(f"RS {p.amount_paid:,.0f}", cell_amount_style),
                    Paragraph(shape_ur(note_str, is_urdu), cell_style)
                ])
            if not s.installments.exists():
                no_p_str = "ابھی کوئی ادائیگی نہیں ہوئی" if is_urdu else "No payments made yet"
                salary_card_data.append([
                    Paragraph(shape_ur(no_p_str, is_urdu), cell_style),
                    "",
                    ""
                ])

            # Separate Summary Rows for Month and Year
            rem_m_color = "#1b5e20" if s.remaining_salary <= 0 else "#b71c1c"
            rem_y_color = "#1b5e20" if s.remaining_yearly_salary <= 0 else "#b71c1c"

            if is_urdu:
                lbl_m_tot = "ماہانہ کل تنخواہ"
                lbl_m_paid = "ماہانہ ادا شدہ"
                lbl_m_rem = "ماہانہ بقایا"
                
                lbl_y_tot = "سالانہ کل تنخواہ"
                lbl_y_paid = "کل ادا شدہ"
                lbl_y_rem = "سالانہ بقایا"
            else:
                lbl_m_tot = "Monthly Total"
                lbl_m_paid = "Paid (Month)"
                lbl_m_rem = "Month Balance"
                
                lbl_y_tot = "Annual Total"
                lbl_y_paid = "Total Paid (Year)"
                lbl_y_rem = "Annual Balance"

            row_month = [
                Paragraph(f"<b>{shape_ur(lbl_m_tot, is_urdu)}:</b><br/>RS {s.total_salary:,.0f}", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_m_paid, is_urdu)}:</b><br/><font color='#1b5e20'><b>RS {s.total_paid:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_m_rem, is_urdu)}:</b><br/><font color='{rem_m_color}'><b>RS {s.remaining_salary:,.0f}</b></font>", card_footer_style),
            ]

            row_year = [
                Paragraph(f"<b>{shape_ur(lbl_y_tot, is_urdu)}:</b><br/>RS {s.effective_yearly_salary:,.0f}", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_y_paid, is_urdu)}:</b><br/><font color='#1b5e20'><b>RS {s.total_paid:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_y_rem, is_urdu)}:</b><br/><font color='{rem_y_color}'><b>RS {s.remaining_yearly_salary:,.0f}</b></font>", card_footer_style),
            ]

            salary_card_data.append(row_month)
            salary_card_data.append(row_year)

            salary_card_table = Table(salary_card_data, colWidths=[180, 180, 180])
            
            table_styles = [
                ('SPAN', (0, 0), (1, 0)),
                ('SPAN', (0, 1), (-1, 1)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#044e3a")), # Deep Emerald Header Block
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#f0f7f3")), # Soft Mint Subheader
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#1f2937")), # Dark Charcoal Table Header
                ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor("#d8ede2")), # Month summary mint tint
                ('LINEABOVE', (0, -2), (-1, -2), 1.5, colors.HexColor("#044e3a")), # Solid Emerald Line
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#fff8e7")), # Year summary gold tint
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor("#c59b27")), # Solid Gold Line
                ('BOX', (0, 0), (-1, -1), 1.8, colors.HexColor("#044e3a")), # Solid Deep Emerald Frame
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ]
            if not s.installments.exists():
                table_styles.append(('SPAN', (0, 3), (-1, 3)))
            else:
                table_styles.append(('GRID', (0, 2), (-1, -3), 1.0, colors.HexColor("#044e3a"))) # 1.0pt Solid Emerald Grid Lines!
                
            salary_card_table.setStyle(TableStyle(table_styles))
            story.append(salary_card_table)
            story.append(Spacer(1, 15))

    doc.build(story, onFirstPage=draw_islamic_pdf_background, onLaterPages=draw_islamic_pdf_background)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"Imam_Salary_Report_{selected_year}_{month or 'annual'}_{pdf_lang}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ==========================================
# 4. EID COLLECTIONS (record-keeping only, excluded from central totals)
# ==========================================

@login_required(login_url='/admin/login/')
def eid_collections_view(request):
    eid_collections = EidCollection.objects.all().order_by('-date')
    eid_collections = filter_by_month_year(eid_collections, 'date', request)

    imam_type = request.GET.get('imam_type')
    if imam_type:
        eid_collections = eid_collections.filter(imam_type=imam_type)

    total_collected = eid_collections.aggregate(total=Sum('amount_collected'))['total'] or 0

    context = {
        'eid_collections': eid_collections,
        'total_collected': total_collected,
        'selected_year': request.GET.get('year', ''),
        'selected_month': request.GET.get('month', ''),
        'selected_imam_type': imam_type or '',
    }
    return render(request, 'eid_collections.html', context)


@login_required(login_url='/admin/login/')
def add_eid_collection(request):
    if request.method == 'POST':
        date = request.POST.get('date')
        eid_name = request.POST.get('eid_name')
        imam_name = request.POST.get('imam_name')
        imam_type = request.POST.get('imam_type')
        amount_collected = request.POST.get('amount_collected')
        notes = request.POST.get('notes', '')

        EidCollection.objects.create(
            date=date,
            eid_name=eid_name,
            imam_name=imam_name,
            imam_type=imam_type,
            amount_collected=amount_collected,
            notes=notes
        )
        messages.success(request, "Eid collection record save ho gaya (Ye central income mein shamil nahi hoga).")
        return redirect('eid_collections')

    return redirect('eid_collections')


@login_required(login_url='/admin/login/')
def update_eid_collection(request, pk):
    collection = get_object_or_404(EidCollection, pk=pk)
    if request.method == 'POST':
        collection.date = request.POST.get('date')
        collection.eid_name = request.POST.get('eid_name')
        collection.imam_name = request.POST.get('imam_name')
        collection.imam_type = request.POST.get('imam_type')
        collection.amount_collected = request.POST.get('amount_collected')
        collection.notes = request.POST.get('notes', '')
        collection.save()
        messages.success(request, "Eid collection record update ho gaya!")
    return redirect('eid_collections')


@login_required(login_url='/admin/login/')
def delete_eid_collection(request, pk):
    collection = get_object_or_404(EidCollection, pk=pk)
    if request.method == 'POST':
        collection.delete()
        messages.success(request, "Eid collection record delete ho gaya!")
    return redirect('eid_collections')


# ==========================================
# 5. WEEKLY INCOME - ADD / EDIT / DELETE
# ==========================================

@login_required(login_url='/admin/login/')
def add_income_view(request):
    if request.method == 'POST':
        date_str = request.POST.get('date')
        
        # Support multi-row batch entries per date
        day_types = request.POST.getlist('day_type[]') or request.POST.getlist('day_type')
        amounts = request.POST.getlist('amount[]') or request.POST.getlist('amount')
        notes_list = request.POST.getlist('notes[]') or request.POST.getlist('notes')

        if date_str and amounts and day_types:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            created_count = 0
            
            for i in range(len(amounts)):
                amt_raw = amounts[i] if i < len(amounts) else None
                dt = day_types[i] if i < len(day_types) else 'OTHER'
                note = notes_list[i] if i < len(notes_list) else ''
                
                if amt_raw and float(amt_raw) > 0:
                    WeeklyIncome.objects.create(
                        date=parsed_date,
                        day_type=dt,
                        amount=float(amt_raw),
                        notes=note
                    )
                    created_count += 1
            
            if created_count > 0:
                messages.success(request, f"{created_count} Weekly Chanda indraj ho gaye ({date_str}).")
            else:
                messages.error(request, "Barae meharbani kam az kam ek valid amount darj karein.")
        else:
            messages.error(request, "Tamam zaroori fields pur karein.")

    return redirect('weekly_income')


@login_required(login_url='/admin/login/')
def update_income(request, pk):
    income = get_object_or_404(WeeklyIncome, pk=pk)
    if request.method == 'POST':
        income.date = request.POST.get('date')
        income.day_type = request.POST.get('day_type')
        income.amount = request.POST.get('amount')
        income.notes = request.POST.get('notes')
        income.save()
        messages.success(request, "Weekly income record update ho gaya!")
    return redirect('weekly_income')


@login_required(login_url='/admin/login/')
def delete_income(request, pk):
    income = get_object_or_404(WeeklyIncome, pk=pk)
    if request.method == 'POST':
        income.delete()
        messages.success(request, "Weekly income record delete ho gaya!")
    return redirect('weekly_income')


# ==========================================
# 6. EXPENSES - ADD / EDIT / DELETE  (category bug fixed)
# ==========================================

@login_required(login_url='/admin/login/')
def add_expense_view(request):
    if request.method == 'POST':
        date_str = request.POST.get('date')
        
        # Support multi-row batch entries per date
        categories = request.POST.getlist('category[]') or request.POST.getlist('category')
        descriptions = request.POST.getlist('description[]') or request.POST.getlist('description')
        amounts = request.POST.getlist('amount[]') or request.POST.getlist('amount')

        if date_str and amounts and categories:
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            created_count = 0
            
            for i in range(len(amounts)):
                amt_raw = amounts[i] if i < len(amounts) else None
                cat = categories[i] if i < len(categories) else 'OTHER'
                desc = descriptions[i] if i < len(descriptions) else ''
                
                if amt_raw and float(amt_raw) > 0 and desc:
                    Expense.objects.create(
                        date=parsed_date,
                        category=cat,
                        description=desc,
                        amount=float(amt_raw)
                    )
                    created_count += 1
            
            if created_count > 0:
                messages.success(request, f"{created_count} Kharache record ho gaye ({date_str}).")
            else:
                messages.error(request, "Barae meharbani valid amount aur tafseel darj karein.")
        else:
            messages.error(request, "Tamam zaroori fields pur karein.")

    return redirect('expenses')


@login_required(login_url='/admin/login/')
def update_expense_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.date = request.POST.get('date')
        expense.category = request.POST.get('category')
        expense.description = request.POST.get('description')
        expense.amount = request.POST.get('amount')
        expense.save()
        messages.success(request, "Kharche ka record update ho gaya!")
    return redirect('expenses')


@login_required(login_url='/admin/login/')
def delete_expense_view(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, "Kharche ka record delete ho gaya!")
    return redirect('expenses')


# ==========================================
# 7. LAND LEASE - ADD / EDIT / DELETE (was completely missing)
# ==========================================

@login_required(login_url='/admin/login/')
def add_land_lease_view(request):
    if request.method == 'POST':
        LandLease.objects.create(
            land_area=request.POST.get('land_area') or "2 Acres",
            tenant_name=request.POST.get('tenant_name'),
            tenant_contact=request.POST.get('tenant_contact'),
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            duration_years=request.POST.get('duration_years') or 1,
            total_agreed_amount=request.POST.get('total_agreed_amount'),
        )
        messages.success(request, "Naya theka record add ho gaya.")
    return redirect('land_lease')


@login_required(login_url='/admin/login/')
def update_land_lease_view(request, pk):
    lease = get_object_or_404(LandLease, pk=pk)
    if request.method == 'POST':
        lease.land_area = request.POST.get('land_area')
        lease.tenant_name = request.POST.get('tenant_name')
        lease.tenant_contact = request.POST.get('tenant_contact')
        lease.start_date = request.POST.get('start_date')
        lease.end_date = request.POST.get('end_date')
        lease.duration_years = request.POST.get('duration_years')
        lease.total_agreed_amount = request.POST.get('total_agreed_amount')
        lease.save()
        messages.success(request, "Theka record update ho gaya!")
    return redirect('land_lease')


@login_required(login_url='/admin/login/')
def delete_land_lease_view(request, pk):
    lease = get_object_or_404(LandLease, pk=pk)
    if request.method == 'POST':
        lease.delete()
        messages.success(request, "Theka record (tamam payments samet) delete ho gaya.")
    return redirect('land_lease')


@login_required(login_url='/admin/login/')
def add_lease_payment_view(request):
    if request.method == 'POST':
        lease_id = request.POST.get('lease_id')
        payment_date = request.POST.get('payment_date')
        amount_received = request.POST.get('amount_received')
        notes = request.POST.get('notes', '')

        if lease_id and amount_received:
            lease_obj = get_object_or_404(LandLease, id=lease_id)
            # Never allow recording more than what's actually remaining
            amount_received = min(float(amount_received), float(lease_obj.remaining_lease_amount))
            LandLeasePayment.objects.create(
                lease=lease_obj,
                payment_date=payment_date,
                amount_received=amount_received,
                notes=notes
            )
            messages.success(request, "Theke ki payment record ho gayi.")

    return redirect('land_lease')


@login_required(login_url='/admin/login/')
def update_lease_payment_view(request, pk):
    payment = get_object_or_404(LandLeasePayment, pk=pk)
    if request.method == 'POST':
        payment_date = request.POST.get('payment_date')
        amount_received = request.POST.get('amount_received')
        notes = request.POST.get('notes', '')

        lease_obj = payment.lease
        other_payments_total = sum(p.amount_received for p in lease_obj.payments.exclude(pk=pk))
        max_allowed = float(lease_obj.total_agreed_amount) - float(other_payments_total)
        amount_received = min(float(amount_received), max_allowed)

        payment.payment_date = payment_date
        payment.amount_received = amount_received
        payment.notes = notes
        payment.save()
        messages.success(request, "Theke ki payment record update ho gayi!")
    return redirect('land_lease')


@login_required(login_url='/admin/login/')
def delete_lease_payment_view(request, pk):
    payment = get_object_or_404(LandLeasePayment, pk=pk)
    if request.method == 'POST':
        payment.delete()
        messages.success(request, "Payment entry delete ho gayi.")
    return redirect('land_lease')


# ==========================================
# 8. MONTHLY FULL FINANCIAL PDF (unchanged logic, still period-based - correct for a report)
# ==========================================

@login_required(login_url='/admin/login/')
def export_monthly_pdf(request, year=None, month=None):
    register_urdu_fonts()
    registered_fonts = pdfmetrics.getRegisteredFontNames()
    import calendar
    now = timezone.now()

    # Get from GET query parameter or argument
    get_year = request.GET.get('year')
    get_month = request.GET.get('month')
    pdf_lang = request.GET.get('lang') or request.GET.get('pdf_lang') or (request.session.get('lang', 'en') if hasattr(request, 'session') and request.session is not None else 'en')
    is_urdu = (pdf_lang == 'ur')

    font_bism = 'UrduNaskh-Bold' if 'UrduNaskh-Bold' in registered_fonts else ('UrduFont-Bold' if 'UrduFont-Bold' in registered_fonts else 'Helvetica-Bold')

    if is_urdu:
        font_normal = 'UrduNastaliq' if 'UrduNastaliq' in registered_fonts else ('UrduFont' if 'UrduFont' in registered_fonts else 'Helvetica')
        font_bold = 'UrduNastaliq' if 'UrduNastaliq' in registered_fonts else ('UrduFont-Bold' if 'UrduFont-Bold' in registered_fonts else 'Helvetica-Bold')
    else:
        font_normal = 'Helvetica'
        font_bold = 'Helvetica-Bold'

    selected_year = year or (int(get_year) if get_year and get_year.isdigit() else None) or now.year
    raw_month = month or get_month

    is_annual = False
    if raw_month and str(raw_month).lower() in ['all', 'annual']:
        is_annual = True
        selected_month = None
    elif not raw_month or str(raw_month).lower() in ['', 'none']:
        selected_month = now.month
    else:
        if isinstance(raw_month, str) and raw_month.isdigit():
            selected_month = int(raw_month)
        elif isinstance(raw_month, int):
            selected_month = raw_month
        else:
            selected_month = now.month

    selected_year = int(selected_year)

    if is_annual:
        month_name = f"سال {selected_year}" if is_urdu else f"Year {selected_year}"
        weekly_incomes = WeeklyIncome.objects.filter(date__year=selected_year).order_by('date')
        expenses = Expense.objects.filter(date__year=selected_year).order_by('date')
        lease_payments = LandLeasePayment.objects.filter(payment_date__year=selected_year).order_by('payment_date')
        salary_payments = ImamSalaryInstallment.objects.filter(payment_date__year=selected_year).order_by('payment_date')
        salaries = ImamSalary.objects.filter(month_year__year=selected_year).order_by('month_year')
        leases = LandLease.objects.filter(
            start_date__year__lte=selected_year,
            end_date__year__gte=selected_year
        ).order_by('start_date')
    else:
        selected_month = int(selected_month)
        if is_urdu:
            month_name = f"{URDU_MONTH_NAMES.get(selected_month, '')} {selected_year}"
        else:
            month_name = datetime(selected_year, selected_month, 1).strftime('%B %Y')
            
        weekly_incomes = WeeklyIncome.objects.filter(date__year=selected_year, date__month=selected_month).order_by('date')
        expenses = Expense.objects.filter(date__year=selected_year, date__month=selected_month).order_by('date')
        lease_payments = LandLeasePayment.objects.filter(payment_date__year=selected_year, payment_date__month=selected_month).order_by('payment_date')
        salary_payments = ImamSalaryInstallment.objects.filter(payment_date__year=selected_year, payment_date__month=selected_month).order_by('payment_date')
        salaries = ImamSalary.objects.filter(month_year__year=selected_year, month_year__month=selected_month).order_by('month_year')
        
        _, last_day = calendar.monthrange(selected_year, selected_month)
        first_date = datetime(selected_year, selected_month, 1).date()
        last_date = datetime(selected_year, selected_month, last_day).date()
        leases = LandLease.objects.filter(
            start_date__lte=last_date,
            end_date__gte=first_date
        ).order_by('start_date')

    # Calculate Totals
    total_weekly = weekly_incomes.aggregate(total=Sum('amount'))['total'] or 0
    total_lease = lease_payments.aggregate(total=Sum('amount_received'))['total'] or 0
    month_total_income = total_weekly + total_lease

    total_gen_expense = expenses.aggregate(total=Sum('amount'))['total'] or 0
    total_salary_paid = salary_payments.aggregate(total=Sum('amount_paid'))['total'] or 0
    month_total_expense = total_gen_expense + total_salary_paid

    net_monthly_balance = month_total_income - month_total_expense

    # Combine Income Items
    income_items = []
    for inc in weekly_incomes:
        source_disp = DAY_TYPE_URDU.get(inc.get_day_type_display(), inc.get_day_type_display()) if is_urdu else inc.get_day_type_display()
        income_items.append({
            'date': inc.date,
            'source': source_disp,
            'notes': inc.notes or "-",
            'amount': inc.amount,
        })
    for lse in lease_payments:
        source_disp = f"زمین کا ٹھیکہ: {translate_user_input_to_urdu(lse.lease.tenant_name)}" if is_urdu else f"Land Lease: {lse.lease.tenant_name}"
        note_disp = lse.notes or ("ٹھیکہ قسط" if is_urdu else "Lease Payment")
        income_items.append({
            'date': lse.payment_date,
            'source': source_disp,
            'notes': note_disp,
            'amount': lse.amount_received,
        })
    income_items.sort(key=lambda x: x['date'])

    # Combine Expense Items
    expense_items = []
    for exp in expenses:
        cat_disp = EXPENSE_CAT_URDU.get(exp.get_category_display(), exp.get_category_display()) if is_urdu else exp.get_category_display()
        expense_items.append({
            'date': exp.date,
            'category': cat_disp,
            'description': exp.description or "-",
            'amount': exp.amount,
        })
    for sal in salary_payments:
        cat_disp = "امام کی تنخواہ" if is_urdu else "Imam Salary"
        if is_urdu:
            sm_name = URDU_MONTH_NAMES.get(sal.salary_record.month_year.month, '')
            desc_disp = f"قسط: {translate_user_input_to_urdu(sal.salary_record.imam_name)} ({sm_name} {sal.salary_record.month_year.year})"
        else:
            desc_disp = f"Installment: {sal.salary_record.imam_name} ({sal.salary_record.month_year.strftime('%b %Y')})"
        expense_items.append({
            'date': sal.payment_date,
            'category': cat_disp,
            'description': desc_disp,
            'amount': sal.amount_paid,
        })
    expense_items.sort(key=lambda x: x['date'])

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    story = []
    styles = getSampleStyleSheet()

    # Authentic Islamic Crest Banner for Bismillah with exact Arabic diacritics & side titles
    bismillah_exact_text = "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"
    bismillah_str = shape_ur(bismillah_exact_text, is_urdu=True)
    allah_str = shape_ur("یا اللہ", is_urdu=True)
    rasool_str = shape_ur("یا رسول اللہ", is_urdu=True)

    bism_center_style = ParagraphStyle(
        'BismCenterM', parent=styles['Normal'], fontName=font_bism, fontSize=16.5, leading=20,
        textColor=colors.HexColor("#fef08a"), alignment=1
    )
    bism_right_style = ParagraphStyle(
        'BismRightM', parent=styles['Normal'], fontName=font_bism, fontSize=14, leading=18,
        textColor=colors.HexColor("#fef08a"), alignment=2
    )
    bism_left_style = ParagraphStyle(
        'BismLeftM', parent=styles['Normal'], fontName=font_bism, fontSize=14, leading=18,
        textColor=colors.HexColor("#fef08a"), alignment=0
    )

    p_left = Paragraph(f"<b>{rasool_str}</b>", bism_left_style)
    p_center = Paragraph(f"<b>{bismillah_str}</b>", bism_center_style)
    p_right = Paragraph(f"<b>{allah_str}</b>", bism_right_style)

    bism_box = Table([[p_left, p_center, p_right]], colWidths=[95, 330, 95])
    bism_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#044e3a")), # Deep Sacred Emerald Fill
        ('BOX', (0, 0), (-1, -1), 2.5, colors.HexColor("#c59b27")), # Outer Metallic Gold Frame
        ('LINEABOVE', (0, 0), (-1, -1), 1.2, colors.HexColor("#fef08a")), # Inner Gold Line Accent
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, colors.HexColor("#fef08a")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(bism_box)
    story.append(Spacer(1, 14))

    # Custom unique styles (Increased font sizes & bold weights for ultra-readable printouts)
    title_style = ParagraphStyle(
        'RepTitle', parent=styles['Heading1'], fontName=font_bold, fontSize=19 if is_urdu else 22, leading=25,
        textColor=colors.HexColor("#044e3a"), alignment=1
    )
    subtitle_style = ParagraphStyle(
        'RepSubtitle', parent=styles['Normal'], fontName=font_bold, fontSize=12.5, leading=16,
        textColor=colors.HexColor("#000000"), alignment=1
    )
    section_style = ParagraphStyle(
        'RepSection', parent=styles['Heading2'], fontName=font_bold, fontSize=16 if is_urdu else 15.5, leading=24 if is_urdu else 20,
        textColor=colors.HexColor("#044e3a"), spaceBefore=18, spaceAfter=9
    )
    cell_style = ParagraphStyle(
        'RepCell', parent=styles['Normal'], fontName=font_bold, fontSize=11 if is_urdu else 11, leading=19 if is_urdu else 15,
        textColor=colors.HexColor("#000000") # Pure solid black bold for maximum print clarity
    )
    cell_hdr_style = ParagraphStyle(
        'RepCellHdr', parent=styles['Normal'], fontName=font_bold, fontSize=11.5 if is_urdu else 11.5, leading=19 if is_urdu else 15,
        textColor=colors.white
    )
    cell_amount_style = ParagraphStyle(
        'RepCellAmt', parent=styles['Normal'], fontName=font_bold, fontSize=11.5 if is_urdu else 11.5, leading=19 if is_urdu else 15,
        textColor=colors.HexColor("#044e3a"), alignment=2
    )

    # Custom styles for Imam & Thekedar Cards
    imam_name_style = ParagraphStyle(
        'ImamName', parent=styles['Normal'], fontName=font_bold, fontSize=13.5, leading=17,
        textColor=colors.white
    )
    thekedar_name_style = ParagraphStyle(
        'ThekedarName', parent=styles['Normal'], fontName=font_bold, fontSize=13.5, leading=17,
        textColor=colors.white
    )
    card_info_style = ParagraphStyle(
        'CardInfo', parent=styles['Normal'], fontName=font_bold, fontSize=10, leading=14,
        textColor=colors.HexColor("#0f172a")
    )
    card_footer_style = ParagraphStyle(
        'CardF', parent=styles['Normal'], fontName=font_bold, fontSize=10, leading=15,
        textColor=colors.HexColor("#0f172a")
    )

    # Document Header Banner Box (Styled matching Bismillah aesthetics)
    hdr_title = "جامع مسجد نور مالیاتی رپورٹ" if is_urdu else "JAMEYA MASJID NOOR FINANCIAL REPORT"
    hdr_sub = f"تفصیلی اسٹیٹمنٹ برائے {month_name}" if is_urdu else f"Detailed Statement for {month_name}"
    
    title_box_style = ParagraphStyle(
        'RepTitleBox', parent=styles['Heading1'], fontName=font_bold, fontSize=18 if is_urdu else 19, leading=24,
        textColor=colors.HexColor("#fef08a"), alignment=1 # Metallic Gold Title Text
    )
    subtitle_box_style = ParagraphStyle(
        'RepSubtitleBox', parent=styles['Normal'], fontName=font_bold, fontSize=12, leading=16,
        textColor=colors.white, alignment=1 # High-contrast White Subtitle Text
    )

    p_title = Paragraph(f"<b>{shape_ur(hdr_title, is_urdu)}</b>", title_box_style)
    p_sub = Paragraph(shape_ur(hdr_sub, is_urdu), subtitle_box_style)

    header_banner_table = Table([[p_title], [p_sub]], colWidths=[520])
    header_banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#044e3a")), # Deep Sacred Emerald Fill
        ('BOX', (0, 0), (-1, -1), 2.2, colors.HexColor("#c59b27")), # Metallic Gold Frame
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#c59b27")), # Golden Divider Accent Line
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(header_banner_table)
    story.append(Spacer(1, 14))

    # Highlighted Hero Summary Cards (Top Section)
    card_title_style = ParagraphStyle(
        'CardT', parent=styles['Normal'], fontName=font_bold, fontSize=11, leading=14,
        textColor=colors.white, alignment=1
    )
    card_val_inc = ParagraphStyle(
        'CardValInc', parent=styles['Normal'], fontName=font_bold, fontSize=15.5, leading=19,
        textColor=colors.HexColor("#fef08a"), alignment=1 # Highlighted Metallic Gold
    )
    card_val_exp = ParagraphStyle(
        'CardValExp', parent=styles['Normal'], fontName=font_bold, fontSize=15.5, leading=19,
        textColor=colors.HexColor("#fee2e2"), alignment=1 # High contrast Rose White
    )
    card_val_net = ParagraphStyle(
        'CardValNet', parent=styles['Normal'], fontName=font_bold, fontSize=15.5, leading=19,
        textColor=colors.HexColor("#e0f2fe") if net_monthly_balance >= 0 else colors.HexColor("#fee2e2"), alignment=1
    )

    lbl_tot_inc = "کل آمدنی" if is_urdu else "TOTAL INCOME"
    lbl_tot_exp = "کل اخراجات" if is_urdu else "TOTAL EXPENSE"
    lbl_net_bal = "خالص بیلنس" if is_urdu else "NET BALANCE"

    summary_data = [
        [
            Paragraph(shape_ur(lbl_tot_inc, is_urdu), card_title_style),
            Paragraph(shape_ur(lbl_tot_exp, is_urdu), card_title_style),
            Paragraph(shape_ur(lbl_net_bal, is_urdu), card_title_style)
        ],
        [
            Paragraph(f"RS {month_total_income:,.0f}", card_val_inc),
            Paragraph(f"RS {month_total_expense:,.0f}", card_val_exp),
            Paragraph(f"RS {net_monthly_balance:,.0f}", card_val_net)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[180, 180, 180])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 1), colors.HexColor("#044e3a")), # Sacred Emerald Fill for HIGHLIGHTED Total Income Card
        ('BACKGROUND', (1, 0), (1, 1), colors.HexColor("#991b1b")), # Rich Dark Crimson Fill for Total Expense Card
        ('BACKGROUND', (2, 0), (2, 1), colors.HexColor("#0369a1") if net_monthly_balance >= 0 else colors.HexColor("#991b1b")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, -1), 2.2, colors.HexColor("#c59b27")), # Metallic Gold Frame around Total Income Card
        ('BOX', (1, 0), (1, -1), 1.8, colors.HexColor("#b71c1c")),
        ('BOX', (2, 0), (2, -1), 1.8, colors.HexColor("#0284c7")),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, colors.HexColor("#fef08a")), # Accent inner line separating title and value
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 15))

    # Income Section
    sec_inc_title = "آمدنی کی تفصیل" if is_urdu else "Income Breakdown (Aamdan Tafseel)"
    story.append(Paragraph(f"<b>{shape_ur(sec_inc_title, is_urdu)}</b>", section_style))
    inc_header_style = ParagraphStyle(
        'IncH', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15, textColor=colors.white
    )
    inc_amount_style = ParagraphStyle(
        'IncAmt', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15,
        textColor=colors.HexColor("#1b5e20"), alignment=2
    )

    h_date = "تاریخ" if is_urdu else "Date"
    h_src = "ذریعہ / قسم" if is_urdu else "Source / Type"
    h_note = "نوٹس / تفصیل" if is_urdu else "Notes / Description"
    h_amt = "رقم" if is_urdu else "Amount"

    inc_rows = [[
        Paragraph(shape_ur(h_date, is_urdu), inc_header_style),
        Paragraph(shape_ur(h_src, is_urdu), inc_header_style),
        Paragraph(shape_ur(h_note, is_urdu), inc_header_style),
        Paragraph(shape_ur(h_amt, is_urdu), inc_header_style)
    ]]

    for item in income_items:
        inc_rows.append([
            Paragraph(item['date'].strftime('%d-%b-%Y'), cell_style),
            Paragraph(shape_ur(item['source'], is_urdu), cell_style),
            Paragraph(shape_ur(item['notes'], is_urdu), cell_style),
            Paragraph(f"RS {item['amount']:,.0f}", inc_amount_style)
        ])

    if not income_items:
        no_inc_msg = "اس عرصے کے لیے کوئی آمدنی کا ریکارڈ نہیں ہے۔" if is_urdu else "No income recorded for this period."
        inc_rows.append([Paragraph(shape_ur(no_inc_msg, is_urdu), cell_style), "", "", ""])
    else:
        tot_inc_lbl = "کل آمدنی" if is_urdu else "TOTAL INCOME"
        total_inc_lbl_style = ParagraphStyle(
            'TotIncLbl', parent=styles['Normal'], fontName=font_bold, fontSize=12.5, leading=16,
            textColor=colors.white
        )
        total_inc_val_style = ParagraphStyle(
            'TotIncVal', parent=styles['Normal'], fontName=font_bold, fontSize=13, leading=16,
            textColor=colors.HexColor("#fef08a"), alignment=2 # High-contrast bright gold total
        )
        inc_rows.append([
            Paragraph(f"<b>{shape_ur(tot_inc_lbl, is_urdu)}</b>", total_inc_lbl_style),
            "", "",
            Paragraph(f"RS {month_total_income:,.0f}", total_inc_val_style)
        ])

    inc_table = Table(inc_rows, colWidths=[90, 130, 190, 110])
    inc_table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#044e3a")), # Deep Emerald Header
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1.2, colors.HexColor("#044e3a")), # 1.2pt Solid Emerald Grid Lines
        ('BOX', (0, 0), (-1, -1), 2.0, colors.HexColor("#044e3a")), # Solid Emerald Frame
        ('TOPPADDING', (0, 0), (-1, -1), 8.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8.5),
    ]
    if not income_items:
        inc_table_style.append(('SPAN', (0, 1), (-1, 1)))
    else:
        inc_table_style.append(('SPAN', (0, -1), (2, -1)))
        inc_table_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#044e3a"))) # HIGHLIGHTED Total Income Cell!
        inc_table_style.append(('LINEABOVE', (0, -1), (-1, -1), 2.0, colors.HexColor("#c59b27"))) # Gold accent line above total

    inc_table.setStyle(TableStyle(inc_table_style))
    story.append(inc_table)
    story.append(Spacer(1, 15))

    # Expense Section
    sec_exp_title = "اخراجات کی تفصیل" if is_urdu else "Expense Breakdown (Kharajaat Tafseel)"
    story.append(Paragraph(f"<b>{shape_ur(sec_exp_title, is_urdu)}</b>", section_style))
    exp_header_style = ParagraphStyle(
        'ExpH', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15, textColor=colors.white
    )
    exp_amount_style = ParagraphStyle(
        'ExpAmt', parent=styles['Normal'], fontName=font_bold, fontSize=11.5, leading=15,
        textColor=colors.HexColor("#b71c1c"), alignment=2
    )

    h_cat = "زمرہ" if is_urdu else "Category"
    h_desc = "تفصیل / دیکھ بھال" if is_urdu else "Description / Details"

    exp_rows = [[
        Paragraph(shape_ur(h_date, is_urdu), exp_header_style),
        Paragraph(shape_ur(h_cat, is_urdu), exp_header_style),
        Paragraph(shape_ur(h_desc, is_urdu), exp_header_style),
        Paragraph(shape_ur(h_amt, is_urdu), exp_header_style)
    ]]

    for item in expense_items:
        exp_rows.append([
            Paragraph(item['date'].strftime('%d-%b-%Y'), cell_style),
            Paragraph(shape_ur(item['category'], is_urdu), cell_style),
            Paragraph(shape_ur(item['description'], is_urdu), cell_style),
            Paragraph(f"RS {item['amount']:,.0f}", exp_amount_style)
        ])

    if not expense_items:
        no_exp_msg = "اس عرصے کے لیے کوئی خرچہ ریکارڈ نہیں ہے۔" if is_urdu else "No expenses recorded for this period."
        exp_rows.append([Paragraph(shape_ur(no_exp_msg, is_urdu), cell_style), "", "", ""])
    else:
        tot_exp_lbl = "کل اخراجات" if is_urdu else "TOTAL EXPENSE"
        total_exp_lbl_style = ParagraphStyle(
            'TotExpLbl', parent=styles['Normal'], fontName=font_bold, fontSize=12.5, leading=16,
            textColor=colors.white
        )
        total_exp_val_style = ParagraphStyle(
            'TotExpVal', parent=styles['Normal'], fontName=font_bold, fontSize=13, leading=16,
            textColor=colors.HexColor("#fee2e2"), alignment=2 # High-contrast bright rose total
        )
        exp_rows.append([
            Paragraph(f"<b>{shape_ur(tot_exp_lbl, is_urdu)}</b>", total_exp_lbl_style),
            "", "",
            Paragraph(f"RS {month_total_expense:,.0f}", total_exp_val_style)
        ])

    exp_table = Table(exp_rows, colWidths=[90, 120, 200, 110])
    exp_table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#991b1b")), # Rich Dark Crimson Header
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 1.0, colors.HexColor("#991b1b")), # 1.0pt Solid Crimson Grid Lines
        ('BOX', (0, 0), (-1, -1), 1.8, colors.HexColor("#991b1b")), # Solid Crimson Frame
        ('TOPPADDING', (0, 0), (-1, -1), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7.5),
    ]
    if not expense_items:
        exp_table_style.append(('SPAN', (0, 1), (-1, 1)))
    else:
        exp_table_style.append(('SPAN', (0, -1), (2, -1)))
        exp_table_style.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#991b1b"))) # HIGHLIGHTED Total Expense Cell!
        exp_table_style.append(('LINEABOVE', (0, -1), (-1, -1), 2.0, colors.HexColor("#c59b27"))) # Gold accent line above total

    exp_table.setStyle(TableStyle(exp_table_style))
    story.append(exp_table)
    story.append(Spacer(1, 20))

    # Imam Salary Section (Cards)
    sec_imam_title = "امام کی تنخواہ کا ریکارڈ" if is_urdu else "Imam Salary Status (Mahnana Tankhah Tafseel)"
    story.append(Paragraph(f"<b>{shape_ur(sec_imam_title, is_urdu)}</b>", section_style))
    if not salaries.exists():
        no_sal_msg = "اس عرصے کے لیے کوئی تنخواہ کا ریکارڈ نہیں مل سکا۔" if is_urdu else "No Imam salary records found for this period."
        story.append(Paragraph(shape_ur(no_sal_msg, is_urdu), cell_style))
        story.append(Spacer(1, 15))
    else:
        for s in salaries:
            if is_urdu:
                status_text = "مکمل ادا شدہ" if s.is_fully_paid else "بقایا"
            else:
                status_text = "FULLY PAID" if s.is_fully_paid else "PENDING"
            status_color = "#a7f3d0" if s.is_fully_paid else "#fecaca"
            status_badge_style = ParagraphStyle(
                'ImamStatus', parent=styles['Normal'], fontName=font_bold, fontSize=10.5, leading=13,
                textColor=colors.HexColor(status_color), alignment=2
            )

            st_prefix = "حالت: " if is_urdu else "STATUS: "
            s_month_name = URDU_MONTH_NAMES.get(s.month_year.month, '') if is_urdu else s.month_year.strftime('%B')
            s_period_str = f"{s_month_name} {s.month_year.year}"
            period_label_text = f"مدت تنخواہ: {s_period_str}" if is_urdu else f"Salary Period: {s_period_str}"

            col1 = "ادائیگی کی تاریخ" if is_urdu else "Payment Date"
            col2 = "ادا شدہ رقم" if is_urdu else "Amount Paid"
            col3 = "تفصیل / اقساط" if is_urdu else "Notes / Details"

            salary_card_data = [
                # Row 0: Imam Name & Status Badge
                [
                    Paragraph(f"<b>{shape_ur(s.imam_name, is_urdu)}</b>", imam_name_style),
                    "",
                    Paragraph(f"<b>{shape_ur(st_prefix + status_text, is_urdu)}</b>", status_badge_style)
                ],
                # Row 1: Subtitle details
                [
                    Paragraph(shape_ur(period_label_text, is_urdu), card_info_style),
                    "",
                    ""
                ],
                # Row 2: Table Header
                [
                    Paragraph(f"<b>{shape_ur(col1, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col2, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col3, is_urdu)}</b>", cell_hdr_style)
                ]
            ]
            
            for p in s.installments.all().order_by('payment_date'):
                note_str = p.notes or ("قسط ادائیگی" if is_urdu else "Installment Payment")
                salary_card_data.append([
                    Paragraph(p.payment_date.strftime('%d-%b-%Y'), cell_style),
                    Paragraph(f"RS {p.amount_paid:,.0f}", cell_amount_style),
                    Paragraph(shape_ur(note_str, is_urdu), cell_style)
                ])
            if not s.installments.exists():
                no_p_str = "ابھی کوئی ادائیگی نہیں ہوئی" if is_urdu else "No payments made yet"
                salary_card_data.append([
                    Paragraph(shape_ur(no_p_str, is_urdu), cell_style),
                    "",
                    ""
                ])

            # Separate Summary Rows for Month and Year
            rem_m_color = "#1b5e20" if s.remaining_salary <= 0 else "#b71c1c"
            rem_y_color = "#1b5e20" if s.remaining_yearly_salary <= 0 else "#b71c1c"

            if is_urdu:
                lbl_m_tot = "ماہانہ کل تنخواہ"
                lbl_m_paid = "ماہانہ ادا شدہ"
                lbl_m_rem = "ماہانہ بقایا"
                
                lbl_y_tot = "سالانہ کل تنخواہ"
                lbl_y_paid = "کل ادا شدہ"
                lbl_y_rem = "سالانہ بقایا"
            else:
                lbl_m_tot = "Monthly Total"
                lbl_m_paid = "Paid (Month)"
                lbl_m_rem = "Month Balance"
                
                lbl_y_tot = "Annual Total"
                lbl_y_paid = "Total Paid (Year)"
                lbl_y_rem = "Annual Balance"

            row_month = [
                Paragraph(f"<b>{shape_ur(lbl_m_tot, is_urdu)}:</b><br/>RS {s.total_salary:,.0f}", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_m_paid, is_urdu)}:</b><br/><font color='#1b5e20'><b>RS {s.total_paid:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_m_rem, is_urdu)}:</b><br/><font color='{rem_m_color}'><b>RS {s.remaining_salary:,.0f}</b></font>", card_footer_style),
            ]

            row_year = [
                Paragraph(f"<b>{shape_ur(lbl_y_tot, is_urdu)}:</b><br/>RS {s.effective_yearly_salary:,.0f}", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_y_paid, is_urdu)}:</b><br/><font color='#1b5e20'><b>RS {s.total_paid:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_y_rem, is_urdu)}:</b><br/><font color='{rem_y_color}'><b>RS {s.remaining_yearly_salary:,.0f}</b></font>", card_footer_style),
            ]

            salary_card_data.append(row_month)
            salary_card_data.append(row_year)

            salary_card_table = Table(salary_card_data, colWidths=[180, 180, 180])
            
            table_styles = [
                ('SPAN', (0, 0), (1, 0)),
                ('SPAN', (0, 1), (-1, 1)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#044e3a")), # Deep Emerald Header Block
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#f0f7f3")), # Soft Mint Subheader
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#1f2937")), # Dark Charcoal Table Header
                ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor("#d8ede2")), # Month summary mint tint
                ('LINEABOVE', (0, -2), (-1, -2), 1.5, colors.HexColor("#044e3a")),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#fff8e7")), # Year summary gold tint
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor("#c59b27")),
                ('BOX', (0, 0), (-1, -1), 1.8, colors.HexColor("#044e3a")), # Solid Deep Emerald Frame
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 7.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7.5),
            ]
            if not s.installments.exists():
                table_styles.append(('SPAN', (0, 3), (-1, 3)))
            else:
                table_styles.append(('GRID', (0, 2), (-1, -3), 1.0, colors.HexColor("#044e3a"))) # 1.0pt Solid Emerald Grid Lines!
                
            salary_card_table.setStyle(TableStyle(table_styles))
            story.append(salary_card_table)
            story.append(Spacer(1, 15))

    # Land Lease Section (Cards)
    sec_lease_title = "زمین کا ٹھیکہ (زمین کا کرایہ)" if is_urdu else "Land Lease Status (Zameen Theka Tafseel)"
    story.append(Paragraph(f"<b>{shape_ur(sec_lease_title, is_urdu)}</b>", section_style))
    if not leases.exists():
        no_lse_msg = "اس عرصے کے لیے کوئی فعال ٹھیکہ ریکارڈ نہیں مل سکا۔" if is_urdu else "No active land leases found for this period."
        story.append(Paragraph(shape_ur(no_lse_msg, is_urdu), cell_style))
        story.append(Spacer(1, 15))
    else:
        for l in leases:
            if is_urdu:
                status_text = "مکمل ادا شدہ" if l.remaining_lease_amount <= 0 else "فعال"
            else:
                status_text = "FULLY PAID" if l.remaining_lease_amount <= 0 else "ACTIVE"
            status_color = "#a7f3d0" if l.remaining_lease_amount <= 0 else "#fef08a"
            status_badge_style = ParagraphStyle(
                'LeaseStatus', parent=styles['Normal'], fontName=font_bold, fontSize=10.5, leading=13,
                textColor=colors.HexColor(status_color), alignment=2
            )

            st_prefix = "حالت: " if is_urdu else "STATUS: "

            if is_urdu:
                st_m = URDU_MONTH_NAMES.get(l.start_date.month, '')
                en_m = URDU_MONTH_NAMES.get(l.end_date.month, '')
                l_info_text = f"رقبہ: {translate_user_input_to_urdu(l.land_area)}  |  مدت: {l.duration_years} سال  |  عرصہ: {st_m} {l.start_date.year} - {en_m} {l.end_date.year}"
            else:
                l_info_text = f"Area: {l.land_area}  |  Duration: {l.duration_years} Years  |  Period: {l.start_date.strftime('%b %Y')} - {l.end_date.strftime('%b %Y')}"

            col1_l = "ادائیگی کی تاریخ" if is_urdu else "Payment Date"
            col2_l = "وصول شدہ رقم" if is_urdu else "Amount Received"
            col3_l = "تفصیل / نوٹس" if is_urdu else "Notes / Details"

            lease_card_data = [
                # Row 0: Tenant Name & Status Badge
                [
                    Paragraph(f"<b>{shape_ur(l.tenant_name, is_urdu)}</b>", thekedar_name_style),
                    "",
                    Paragraph(f"<b>{shape_ur(st_prefix + status_text, is_urdu)}</b>", status_badge_style)
                ],
                # Row 1: Subtitle details
                [
                    Paragraph(shape_ur(l_info_text, is_urdu), card_info_style),
                    "",
                    ""
                ],
                # Row 2: Table Header
                [
                    Paragraph(f"<b>{shape_ur(col1_l, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col2_l, is_urdu)}</b>", cell_hdr_style),
                    Paragraph(f"<b>{shape_ur(col3_l, is_urdu)}</b>", cell_hdr_style)
                ]
            ]
            
            for p in l.payments.all().order_by('payment_date'):
                note_str = p.notes or ("ٹھیکہ قسط" if is_urdu else "Lease Payment")
                lease_card_data.append([
                    Paragraph(p.payment_date.strftime('%d-%b-%Y'), cell_style),
                    Paragraph(f"RS {p.amount_received:,.0f}", cell_amount_style),
                    Paragraph(shape_ur(note_str, is_urdu), cell_style)
                ])
            if not l.payments.exists():
                no_lp_str = "ابھی کوئی ادائیگی موصول نہیں ہوئی" if is_urdu else "No payments received yet"
                lease_card_data.append([
                    Paragraph(shape_ur(no_lp_str, is_urdu), cell_style),
                    "",
                    ""
                ])

            # Bottom Summary Row with Large Totals
            rem_color = "#1b5e20" if l.remaining_lease_amount <= 0 else "#b71c1c"
            lbl_ta = "کل طے شدہ" if is_urdu else "Total Agreed"
            lbl_tr_l = "کل وصول شدہ" if is_urdu else "Total Received"
            lbl_rem_l = "بقایا" if is_urdu else "Remaining"

            summary_row = [
                Paragraph(f"<b>{shape_ur(lbl_ta, is_urdu)}:</b><br/><font size='11.5' color='#0f172a'><b>RS {l.total_agreed_amount:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_tr_l, is_urdu)}:</b><br/><font size='11.5' color='#1b5e20'><b>RS {l.total_received:,.0f}</b></font>", card_footer_style),
                Paragraph(f"<b>{shape_ur(lbl_rem_l, is_urdu)}:</b><br/><font size='11.5' color='{rem_color}'><b>RS {l.remaining_lease_amount:,.0f}</b></font>", card_footer_style)
            ]
            lease_card_data.append(summary_row)

            lease_card_table = Table(lease_card_data, colWidths=[180, 180, 180])
            
            lease_table_styles = [
                ('SPAN', (0, 0), (1, 0)),
                ('SPAN', (0, 1), (-1, 1)),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#856404")), # Metallic Gold Header Block
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#fff8e7")), # Light Gold Subheader
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor("#1f2937")), # Dark Charcoal Table Header
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#fff8e7")), # Gold Summary Block
                ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor("#c59b27")),
                ('BOX', (0, 0), (-1, -1), 1.8, colors.HexColor("#c59b27")), # Solid Gold Frame
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 7.5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7.5),
            ]
            if not l.payments.exists():
                lease_table_styles.append(('SPAN', (0, 3), (-1, 3)))
            else:
                lease_table_styles.append(('GRID', (0, 2), (-1, -2), 1.0, colors.HexColor("#c59b27"))) # 1.0pt Solid Gold Grid Lines!
                
            lease_card_table.setStyle(TableStyle(lease_table_styles))
            story.append(lease_card_table)
            story.append(Spacer(1, 15))

    doc.build(story, onFirstPage=draw_islamic_pdf_background, onLaterPages=draw_islamic_pdf_background)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"Masjid_Detailed_Report_{selected_year}_{selected_month or 'annual'}_{pdf_lang}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

