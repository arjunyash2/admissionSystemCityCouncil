from io import BytesIO

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods

from .forms import CustomUserCreationForm, ChildForm, SchoolForm, ManualApplicationForm
from .models import Child, Application, School, CustomUser
from .utils import fetch_school_details
from datetime import date
from django.urls import reverse
import json
import re
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import JsonResponse

from PIL import Image
from pdf2image import convert_from_path
from .utils import create_pdf_template, extract_details_from_text, ocr_from_image


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


# Parental Login - Child
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


# @login_required
# def child_details_view(request):
#     children = Child.objects.filter(parent=request.user)
#     for child in children:
#         child.age = calculate_age(child.dob)
#     return render(request, 'dashboard.html', {'children': children})

@login_required
def child_details_view(request):
    children = Child.objects.filter(parent=request.user)
    children_with_applications = []
    for child in children:
        child.age = calculate_age(child.dob)
        has_application = Application.objects.filter(child=child).exists()
        children_with_applications.append({
            'child': child,
            'has_application': has_application
        })
    return render(request, 'dashboard.html', {'children_with_applications': children_with_applications})




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


# Parental Login - Application To Schools
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


# Parental Login - Application success Page
@login_required
def application_success(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    return render(request, 'application_success.html', {'child': child})


# Parental Login - Application Tracking
@login_required
def application_tracking(request, child_id):
    child = get_object_or_404(Child, id=child_id)
    applications = Application.objects.filter(child=child)

    # Function to determine progress steps for an application
    def get_progress_steps(application):
        return [
            {'status': 'submitted', 'label': 'Application Submitted', 'is_active': application.status in ['submitted', 'in_progress', 'offer_received', 'offer_accepted']},
            {'status': 'in_progress', 'label': 'In Process', 'is_active': application.status in ['in_progress', 'offer_received', 'offer_accepted']},
            {'status': 'offer_received', 'label': 'Offer Received', 'is_active': application.status in ['offer_received', 'offer_accepted']},
            {'status': 'offer_accepted', 'label': 'Offer Accepted', 'is_active': application.status == 'offer_accepted'},
        ]

    # Create a dictionary to hold applications and their progress steps
    applications_with_progress = [
        {'application': application, 'progress_steps': get_progress_steps(application)}
        for application in applications
    ]

    return render(request, 'application_tracking.html', {
        'child': child,
        'applications_with_progress': applications_with_progress
    })


# views.py
@login_required
@require_http_methods(["GET", "POST"])
def edit_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)

    if request.method == 'POST':
        # Update application details
        application.status = request.POST.get('status', application.status)
        # Handle other fields that need to be updated
        # For example, updating preferences (assuming a JSON field)
        application.preferences = request.POST.get('preferences', application.preferences)
        application.save()
        return JsonResponse({'success': True})

    return JsonResponse({
        'application_id': application.id,
        'child_name': application.child.name,
        'status': application.status,
        'applied_on': application.applied_on.strftime('%B %d, %Y, %I:%M %p'),
        'preferences': application.preferences,
        # Add other fields to return here
    })
@login_required
def delete_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    child_id = application.child.id
    application.delete()
    return redirect('application_tracking', child_id=child_id)


# Parental Login - application download
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
    i = 0
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


# Admin Part - Council Views


# Add admin check
def is_admin(user):
    return user.is_admin


@login_required
@user_passes_test(is_admin)
def manage_applications(request):
    applications = Application.objects.all()
    return render(request, 'admin/manage_applications.html', {'applications': applications})


@login_required
def view_application_details(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    child = application.child
    parent = child.parent

    response_data = {
        'application_id': application.id,
        'child_name': child.name,
        'child_dob': child.dob,
        'child_age': calculate_age(child.dob),
        'child_nhs_number': child.nhs_number,
        'child_gender': child.gender,
        'parent_name': f"{parent.forename} {parent.surname}",
        'parent_email': parent.email,
        'parent_phone': parent.mobile_phone,
        'preferences': application.preferences,
        'applied_on': application.applied_on.strftime('%B %d, %Y, %I:%M %p'),
        'status': application.status,
    }

    return JsonResponse(response_data)

# @login_required
# def parent_view_application_details(request, application_id):
#     application = get_object_or_404(Application, id=application_id)
#     child = application.child
#     parent = child.parent
#
#     response_data = {
#         'application_id': application.id,
#         'child_name': child.name,
#         'child_dob': child.dob,
#         'child_age': calculate_age(child.dob),
#         'child_nhs_number': child.nhs_number,
#         'child_gender': child.gender,
#         'parent_name': f"{parent.forename} {parent.surname}",
#         'parent_email': parent.email,
#         'parent_phone': parent.mobile_phone,
#         'preferences': application.preferences,
#         'applied_on': application.applied_on.strftime('%B %d, %Y, %I:%M %p'),
#         'status': application.status
#     }
#
#     return JsonResponse(response_data)


@login_required
@user_passes_test(is_admin)
def add_manual_application(request):
    if request.method == 'POST':
        form = ManualApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            text = ocr_from_image(file)

            extracted_data = parse_application_text(text)
            child_id = generate_unique_child_id()

            child_data = {
                'name': extracted_data['child_name'],
                'dob': extracted_data['child_dob'],
                'gender': extracted_data['child_gender'],
                'nhs_number': extracted_data['child_nhs']
            }

            parent_data = {
                'email': extracted_data['parent_email'],
                'title': extracted_data['parent_title'],
                'forename': extracted_data['parent_forename'],
                'surname': extracted_data['parent_surname'],
                'sex': extracted_data['parent_sex'],
                'address': extracted_data['parent_address'],
                'phone': extracted_data['parent_phone']
            }

            preferences = extracted_data['preferences']

            request.session['child_data'] = child_data
            request.session['parent_data'] = parent_data
            request.session['preferences'] = preferences
            request.session['child_id'] = child_id

            return redirect('admin/confirm_manual_application')
    else:
        form = ManualApplicationForm()
    return render(request, 'admin/add_manual_application.html', {'form': form})


def generate_unique_child_id():
    last_child = Child.objects.order_by('id').last()
    if last_child:
        return last_child.id + 1
    else:
        return 1


def parse_application_text(text):
    # Extract details using regular expressions
    parent_email = re.search(r'Email Address:\s*(.*)', text).group(1)
    parent_title = re.search(r'Title \(Mr/Mrs\):\s*(.*)', text).group(1)
    parent_forename = re.search(r'Forename:\s*(.*)', text).group(1)
    parent_surname = re.search(r'Surname:\s*(.*)', text).group(1)
    parent_sex = re.search(r'Sex \(Male/Female\):\s*(.*)', text).group(1)
    parent_address = re.search(r'Address:\s*(.*)', text).group(1)
    parent_phone = re.search(r'Phone Number:\s*(.*)', text).group(1)

    child_name = re.search(r'Name:\s*(.*)', text).group(1)
    child_dob = re.search(r'Date of Birth:\s*(.*)', text).group(1)
    child_gender = re.search(r'Gender:\s*(.*)', text).group(1)
    child_nhs = re.search(r'NHS Number:\s*(.*)', text).group(1)

    preferences = []
    for i in range(1, 4):
        school_name = re.search(rf'School {i} Name:\s*(.*)', text).group(1)
        sibling_name = re.search(rf'Sibling {i} Name:\s*(.*)', text).group(1)
        sibling_dob = re.search(rf'Sibling {i} Date of Birth:\s*(.*)', text).group(1)
        sibling_year_group = re.search(rf'Sibling {i} Year Group:\s*(.*)', text).group(1)
        preferences.append({
            'school_name': school_name,
            'sibling_name': sibling_name,
            'sibling_dob': sibling_dob,
            'sibling_year_group': sibling_year_group
        })

    return {
        'parent_email': parent_email,
        'parent_title': parent_title,
        'parent_forename': parent_forename,
        'parent_surname': parent_surname,
        'parent_sex': parent_sex,
        'parent_address': parent_address,
        'parent_phone': parent_phone,
        'child_name': child_name,
        'child_dob': child_dob,
        'child_gender': child_gender,
        'child_nhs': child_nhs,
        'preferences': preferences
    }


@login_required
@user_passes_test(is_admin)
def confirm_manual_application(request):
    child_data = request.session.get('child_data')
    parent_data = request.session.get('parent_data')
    preferences = request.session.get('preferences')
    child_id = request.session.get('child_id')

    if request.method == 'POST':
        # Save parent, child, and application data to the database
        parent = CustomUser.objects.create(
            email=parent_data['email'],
            title=parent_data['title'],
            forename=parent_data['forename'],
            surname=parent_data['surname'],
            sex=parent_data['sex'],
            address=parent_data['address'],
            phone=parent_data['phone'],
            username=f"{parent_data['forename']}_{parent_data['surname']}_{child_id}",
            is_parent=True
        )
        child = Child.objects.create(
            id=child_id,
            parent=parent,
            name=child_data['name'],
            dob=child_data['dob'],
            gender=child_data['gender'],
            nhs_number=child_data['nhs_number']
        )
        all_preferences = []
        for index, preference in enumerate(preferences):
            school_name = preference['school_name']
            sibling_name = preference['sibling_name']
            sibling_dob = preference['sibling_dob']
            sibling_year_group = preference['sibling_year_group']

            school = get_object_or_404(School, name=school_name)
            siblings = []
            if sibling_name and sibling_dob and sibling_year_group:
                siblings.append({
                    'name': sibling_name,
                    'dob': sibling_dob,
                    'year_group': sibling_year_group
                })

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
                'siblings': siblings
            })

        Application.objects.create(
            child=child,
            preferences=all_preferences
        )

        return redirect('admin/manage_applications')

    return render(request, 'admin/confirm_manual_application.html', {
        'child_data': child_data,
        'parent_data': parent_data,
        'preferences': preferences
    })


@login_required
@user_passes_test(is_admin)
def manage_schools(request):
    schools = School.objects.all()
    return render(request, 'admin/manage_schools.html', {'schools': schools})


@login_required
@user_passes_test(is_admin)
def add_school(request):
    if request.method == 'POST':
        form = SchoolForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('manage_schools')
    else:
        form = SchoolForm()
    return render(request, 'admin/add_school.html', {'form': form})


# Check if the user is admin
def is_admin(user):
    return user.is_admin


# Admin login view
def admin_login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_admin:
            login(request, user)
            return redirect(reverse('manage_applications'))  # Redirect to the admin dashboard
        else:
            return render(request, 'admin_login.html', {'error': 'Invalid username or password'})
    return render(request, 'admin_login.html')


@login_required
@user_passes_test(is_admin)
def download_pdf_template(request):
    file_path = "admission_form_template.pdf"
    create_pdf_template(file_path)

    with open(file_path, 'rb') as pdf:
        response = HttpResponse(pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="admission_form_template.pdf"'
        return response
