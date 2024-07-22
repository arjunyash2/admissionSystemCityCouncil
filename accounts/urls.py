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
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('delete_child/<int:child_id>/', views.delete_child_view, name='delete_child'),
    path('apply_school/', views.apply_school, name='apply_school'),
    path('application_success/<int:child_id>/', views.application_success, name='application_success'),
    path('application_tracking/<int:child_id>/', views.application_tracking, name='application_tracking'),
    path('download_application/<int:application_id>/', views.download_application, name='download_application'),
    path('', include('django.contrib.auth.urls')),
]


