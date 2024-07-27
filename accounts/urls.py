from django.urls import path, include
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register_success/', views.register_success_view, name='register_success'),
    path('add_child/', views.add_child_view, name='add_child'),
    path('dashboard/', views.child_details_view, name='dashboard'),
    path('child_details/', views.child_details_view, name='child_details'),
    path('profile/', views.profile_view, name='profile'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('delete_child/<int:child_id>/', views.delete_child_view, name='delete_child'),
    path('apply_school/', views.apply_school, name='apply_school'),
    path('application_success/<int:child_id>/', views.application_success, name='application_success'),
    path('application_tracking/<int:child_id>/', views.application_tracking, name='application_tracking'),
    path('download_application/<int:application_id>/', views.download_application, name='download_application'),
    path('admin/manage_applications/', views.manage_applications, name='manage_applications'),
    path('admin/view_application_details/<int:application_id>/', views.view_application_details, name='view_application_details'),
    path('admin/add_manual_application/', views.add_manual_application, name='add_manual_application'),
    path('admin/manage_schools/', views.manage_schools, name='manage_schools'),
    path('admin/add_school/', views.add_school, name='add_school'),
    path('admin/login/', views.admin_login_view, name='admin_login'),
    path('admin/add_manual_application/', views.add_manual_application, name='add_manual_application'),
    path('admin/confirm_manual_application/', views.confirm_manual_application, name='confirm_manual_application'),
    path('admin/download_pdf_template/', views.download_pdf_template, name='download_pdf_template'),
    path('edit_application/<int:application_id>/', views.edit_application, name='edit_application'),
    path('delete_application/<int:application_id>/', views.delete_application, name='delete_application'),

    path('', include('django.contrib.auth.urls')),
]


