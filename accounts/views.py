from io import BytesIO

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, ChildForm
from .models import Child, Application, School
from .utils import fetch_school_details
from datetime import date
from django.urls import reverse
import json
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


def calculate_age(dob):
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


def home_view(request):
    return render(request, 'home.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('child_details')  # Redirect to child details page after login
        else:
            # Return an 'invalid login' error message.
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    return render(request, 'login.html')


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            print("User created and logged in.")
            return redirect('register_success')  # Redirect to success page after registration
        else:
            print("Form is not valid")
            print(form.errors)
    else:
        form = CustomUserCreationForm()
    return render(request, 'register.html', {'form': form})


def register_success_view(request):
    return render(request, 'register_success.html')


def add_child_view(request):
    if request.method == 'POST':
        form = ChildForm(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            child.parent = request.user
            child.save()
            return redirect('child_details')
    else:
        form = ChildForm()
    return render(request, 'add_child.html', {'form': form})


@login_required
def child_details_view(request):
    children = Child.objects.filter(parent=request.user)
    for child in children:
        child.age = calculate_age(child.dob)
    return render(request, 'dashboard.html', {'children': children})


@login_required
def delete_child_view(request, child_id):
    print(f"Attempting to delete child with ID: {child_id}")
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    if request.method == 'POST':
        print(f"Deleting child with ID: {child.id}")
        child.delete()
        return redirect('dashboard')
    print(f"Delete request not POST")
    return render(request, 'dashboard.html')






@login_required
def apply_school(request):
    if request.method == 'POST':
        selected_school_ids = request.POST.get('selected_school_ids').split(',')
        child_id = request.POST.get('child_id')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        sibling_data = json.loads(request.POST.get('sibling_data', '[]'))

        print('Selected School IDs:', selected_school_ids)
        print('Child ID:', child_id)
        print('Latitude:', latitude)
        print('Longitude:', longitude)
        print('Sibling Data:', sibling_data)

        if not child_id:
            return redirect('dashboard')

        child = get_object_or_404(Child, id=child_id)

        all_preferences = []

        for index, place_id in enumerate(selected_school_ids):
            school_details = fetch_school_details(place_id, latitude, longitude)
            print('School Details:', school_details)

            if school_details is None:
                print(f"No details found for school with ID {place_id}")
                continue

            school, created = School.objects.get_or_create(
                here_place_id=place_id,
                defaults={
                    'name': school_details['name'],
                    'address': school_details['address'],
                    'latitude': school_details['latitude'],
                    'longitude': school_details['longitude'],
                    'distance': school_details['distance'],
                    'phone': school_details['phone'],
                    'website': school_details['website'],
                    'email': school_details['email']
                }
            )

            # Find matching sibling data for the current preference using school ID
            siblings_for_preference = []
            for sibling_info in sibling_data:
                if sibling_info['preference'] == index + 1:
                    for sibling in sibling_info['siblings']:
                        if sibling['school_id'] == place_id:
                            siblings_for_preference.append(sibling)

            print(
                f"Adding preference for child {child_id} at school {school.name} with preference {index + 1} and siblings {siblings_for_preference}")

            all_preferences.append({
                'school': {
                    'name': school.name,
                    'address': school.address,
                    'latitude': school.latitude,
                    'longitude': school.longitude,
                    'distance': school.distance,
                    'phone': school.phone,
                    'website': school.website,
                    'email': school.email,
                },
                'preference': index + 1,
                'siblings': siblings_for_preference
            })

            # Create one Application object and update with all preferences and siblings
        application = Application.objects.create(
            child=child,
            preferences=all_preferences
        )

        return redirect('application_success', child_id=child.id)

    return redirect('dashboard')


@login_required
def application_success(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    return render(request, 'application_success.html', {'child': child})


@login_required
def application_tracking(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    applications = Application.objects.filter(child=child)

    return render(request, 'application_tracking.html', {
        'child': child,
        'applications': applications
    })


def download_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="application_{application.id}.pdf"'

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica", 12)

    p.drawString(100, 750, f"Application ID: {application.id}")
    p.drawString(100, 735, f"Child: {application.child.name}")
    p.drawString(100, 720, f"Applied On: {application.applied_on.strftime('%B %d, %Y, %I:%M %p')}")
    i=0
    y_position = 700
    for preference in application.preferences:

        school = preference['school']
        siblings = preference['siblings']

        p.drawString(100, y_position, f"School: {school['name']}")
        p.drawString(100, y_position - 15, f"School Address: {school['address']}")
        p.drawString(100, y_position - 30, f"School Contact: {school['phone'] or 'N/A'}")
        p.drawString(100, y_position - 45, f"School Website: {school['website'] or 'N/A'}")
        p.drawString(100, y_position - 60, f"School Email: {school['email'] or 'N/A'}")
        p.drawString(100, y_position - 75, f"Preference: {preference['preference']}")

        y_position -= 90

        if siblings:
            p.drawString(100, y_position, "Siblings:")
            y_position -= 15

            for sibling in siblings:
                p.drawString(100, y_position, f"    Name: {sibling.get('name')}")
                p.drawString(100, y_position - 15, f"    Date of Birth: {sibling.get('dob')}")
                p.drawString(100, y_position - 30, f"    Year Group: {sibling.get('year_group')}")
                y_position -= 45

        y_position -= 30

    p.showPage()
    p.save()

    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')

def profile_view(request):
    return render(request, 'profile.html')


def logout_view(request):
    logout(request)
    return redirect('login')


# views.py
@login_required
def application_success(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    return render(request, 'application_success.html', {'child': child})
