from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'incomes', views.WeeklyIncomeViewSet, basename='api-income')
router.register(r'weekly-incomes', views.WeeklyIncomeViewSet, basename='api-weekly-income-alt')
router.register(r'expenses', views.ExpenseViewSet, basename='api-expense')
router.register(r'eid-collections', views.EidCollectionViewSet, basename='api-eid-collection')
router.register(r'land-leases', views.LandLeaseViewSet, basename='api-land-lease')
router.register(r'land-lease-payments', views.LandLeasePaymentViewSet, basename='api-land-lease-payment')
router.register(r'lease-payments', views.LandLeasePaymentViewSet, basename='api-lease-payment-alt')
router.register(r'imam-salaries', views.ImamSalaryViewSet, basename='api-imam-salary')
router.register(r'imam-salary-installments', views.ImamSalaryInstallmentViewSet, basename='api-imam-salary-installment')
router.register(r'imam-installments', views.ImamSalaryInstallmentViewSet, basename='api-imam-installment-alt')

api_urlpatterns = [
    path("ping/", views.PingView.as_view(), name="api-ping"),
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="api-logout"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="api-change-password"),
    path("meta/", views.MetaView.as_view(), name="api-meta"),
    path("dashboard/", views.DashboardView.as_view(), name="api-dashboard"),
    path("reports/monthly-pdf/", views.MonthlyPdfView.as_view(), name="api-monthly-pdf"),
    path("reports/imam-salary-pdf/", views.ImamSalaryPdfView.as_view(), name="api-imam-salary-pdf"),
    path("", include(router.urls)),
]

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('set-language/', views.set_language, name='set_language'),



    # Weekly Income
    path('weekly-income/', views.weekly_income_view, name='weekly_income'),
    path('add-income/', views.add_income_view, name='add_income'),
    path('weekly-income/update/<int:pk>/', views.update_income, name='update_income'),
    path('weekly-income/delete/<int:pk>/', views.delete_income, name='delete_income'),

    # Expenses
    path('expenses/', views.expenses_view, name='expenses'),
    path('add-expense/', views.add_expense_view, name='add_expense'),
    path('expenses/update/<int:pk>/', views.update_expense_view, name='update_expense'),
    path('expenses/delete/<int:pk>/', views.delete_expense_view, name='delete_expense'),

    # Land Lease
    path('land-lease/', views.land_lease_view, name='land_lease'),
    path('land-lease/add/', views.add_land_lease_view, name='add_land_lease'),
    path('land-lease/update/<int:pk>/', views.update_land_lease_view, name='update_land_lease'),
    path('land-lease/delete/<int:pk>/', views.delete_land_lease_view, name='delete_land_lease'),
    path('land-lease/payment/add/', views.add_lease_payment_view, name='add_lease_payment'),
    path('land-lease/payment/update/<int:pk>/', views.update_lease_payment_view, name='update_lease_payment'),
    path('land-lease/payment/delete/<int:pk>/', views.delete_lease_payment_view, name='delete_lease_payment'),

    # Imam Salary
    path('imam-salary/', views.imam_salary_view, name='imam_salary'),
    path('imam-salary/add/', views.add_imam_salary_view, name='add_imam_salary'),
    path('imam-salary/update/<int:pk>/', views.update_imam_salary_view, name='update_imam_salary'),
    path('imam-salary/delete/<int:pk>/', views.delete_imam_salary_view, name='delete_imam_salary'),
    path('imam-salary/installment/add/', views.add_imam_installment_view, name='add_imam_installment'),
    path('imam-salary/installment/update/<int:pk>/', views.update_imam_installment_view, name='update_imam_installment'),
    path('imam-salary/installment/delete/<int:pk>/', views.delete_imam_installment_view, name='delete_imam_installment'),
    path('imam-salary/export-pdf/', views.export_imam_salary_pdf, name='export_imam_salary_pdf'),

    # Eid Collections
    path('eid-collections/', views.eid_collections_view, name='eid_collections'),
    path('eid-collections/add/', views.add_eid_collection, name='add_eid_collection'),
    path('eid-collections/update/<int:pk>/', views.update_eid_collection, name='update_eid_collection'),
    path('eid-collections/delete/<int:pk>/', views.delete_eid_collection, name='delete_eid_collection'),

    # Reports
    path('export-pdf/', views.export_monthly_pdf, name='export_monthly_pdf'),
    path('export-pdf/<int:year>/<int:month>/', views.export_monthly_pdf, name='export_monthly_pdf_param'),


    # REST API endpoints (/api/...)
    path('api/', include(api_urlpatterns)),

    path("ping/", views.PingView.as_view(), name="api-ping"),
    path("auth/login/", views.LoginView.as_view(), name="api-login"),
    path("auth/logout/", views.LogoutView.as_view(), name="api-logout"),
    path("auth/me/", views.MeView.as_view(), name="api-me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="api-change-password"),
    path("meta/", views.MetaView.as_view(), name="api-meta"),
    path("dashboard/", views.DashboardView.as_view(), name="api-dashboard"),
    path("reports/monthly-pdf/", views.MonthlyPdfView.as_view(), name="api-monthly-pdf"),
    path("reports/imam-salary-pdf/", views.ImamSalaryPdfView.as_view(), name="api-imam-salary-pdf"),
    path("", include(router.urls)),
]