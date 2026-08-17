from django.urls import path
from . import views

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
]