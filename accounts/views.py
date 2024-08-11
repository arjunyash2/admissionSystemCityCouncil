from io import BytesIO

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from .forms import CustomUserCreationForm, ChildForm, SchoolForm, ManualApplicationForm
from .models import Child, Application, School, CustomUser, Notification
from .utils import fetch_school_details, extract_text_from_pdf
from datetime import date
from django.urls import reverse
import json
import re
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import JsonResponse
import requests

from PIL import Image
from pdf2image import convert_from_path
from .utils import create_pdf_template, extract_details_from_text, ocr_from_image
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from .models import Application, School



def calculate_age(dob):
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age


def home_view(request):
    return render(request, 'home.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if 'send_otp' in request.POST:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                # Generate OTP
                otp = get_random_string(length=6, allowed_chars='1234567890')
                user.otp = otp
                user.save()

                # Send OTP via email
                send_mail(
                    'Your OTP Code',
                    f'Your OTP code is {otp}',
                    settings.EMAIL_HOST_USER,
                    [user.email],
                    fail_silently=False,
                )

                return render(request, 'login.html', {'otp_sent': True, 'username': username, 'password': password})
            else:
                return render(request, 'login.html', {'error': 'Invalid username or password'})

        elif 'login' in request.POST:
            otp = request.POST.get('otp')
            user = CustomUser.objects.get(username=username)

            if otp == user.otp:
                authenticate(request, username=username, password=password)
                login(request, user)
                return redirect('dashboard')
            else:
                return render(request, 'login.html',
                              {'otp_sent': True, 'error': 'Invalid OTP', 'username': username, 'password': password})

    return render(request, 'login.html')


@require_POST
def verify_otp_ajax(request):
    data = json.loads(request.body)
    username = data.get('username')
    otp = data.get('otp')

    try:
        user = CustomUser.objects.get(username=username)
        if user.otp == otp:
            return JsonResponse({'valid': True})
    except CustomUser.DoesNotExist:
        pass

    return JsonResponse({'valid': False})
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
            return redirect('manage_children')
    else:
        form = ChildForm()
    return render(request, 'add_child.html', {'form': form})


@login_required
def manage_children(request):
    children = Child.objects.filter(parent=request.user)
    children_with_applications = []
    for child in children:
        child.age = calculate_age(child.dob)
        has_application = Application.objects.filter(child=child).exists()
        children_with_applications.append({
            'child': child,
            'has_application': has_application
        })
    return render(request, 'manage_children.html', {'children_with_applications': children_with_applications})
@login_required
def child_details_view(request):
    user = request.user
    postcode = user.postcode

    # Fetch latitude and longitude using FindThatPostcode API
    url_postcode = f"https://findthatpostcode.uk/postcodes/{postcode}.json"
    response = requests.get(url_postcode)
    data = response.json()

    lat = data['data']['attributes']['location']['lat']
    lng = data['data']['attributes']['location']['lon']

    # Fetch nearby schools using HERE API
    api_key = 'iW9ceziSt7BhDuG3FZGbuRkk09ETfoDJznAqwbcjMBw'  # Make sure your HERE API key is stored in settings.py
    url_here = f'https://discover.search.hereapi.com/v1/discover?at={lat},{lng}&q=schools&limit=5&apiKey={api_key}'

    response_here = requests.get(url_here)
    schools_data = response_here.json()

    nearby_schools = []

    for school in schools_data.get('items', []):
        # Initialize website as None
        website = None

        # Extract website if available
        for contact in school.get('contacts', []):
            for www in contact.get('www', []):
                website = www.get('value')
                break  # Take the first available website

        nearby_schools.append({
            'title': school['title'],
            'address': school['address']['label'],
            'distance': school['distance'],
            'website': website,
        })


    children = Child.objects.filter(parent=request.user)
    children_with_applications = []

    total_applications = 0
    applications_in_progress = 0
    applications_offer_received = 0
    applications_offer_accepted = 0
    for child in children:
        child.age = calculate_age(child.dob)
        applications = Application.objects.filter(child=child)
        has_application = Application.objects.filter(child=child).exists()
        children_with_applications.append({
            'child': child,
            'has_application': has_application
        })
        total_applications += applications.count()
        applications_in_progress += applications.filter(status='in_progress').count()
        applications_offer_received += applications.filter(status='offer_received').count()
        applications_offer_accepted += applications.filter(status='offer_accepted').count()

    context = {
        'children_with_applications': children_with_applications,
        'total_applications': total_applications,
        'applications_in_progress': applications_in_progress,
        'applications_offer_received': applications_offer_received,
        'applications_offer_accepted': applications_offer_accepted,
        'nearby_schools': nearby_schools,  # Add nearby schools to context
    }

    return render(request, 'dashboard.html', context)


@login_required
def delete_child(request, child_id):
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    if request.method == "POST":
        child.delete()
        return redirect('manage_children')  # Redirect to the children management page after deletion
    return redirect('manage_children')  # If not POST, redirect back without deleting

def send_application_email(child, application_details):
    subject = 'Application Submitted'

    details = "\n\n".join([
        f"Preference {detail['preference']}:\n"
        f"School Name: {detail['school']['name']}\n"
        f"Address: {detail['school']['address']}\n"
        f"Latitude: {detail['school']['latitude']}\n"
        f"Longitude: {detail['school']['longitude']}\n"
        f"Distance: {detail['school']['distance']} meters\n"
        f"Phone: {detail['school']['phone']}\n"
        f"Website: {detail['school']['website']}\n"
        f"Email: {detail['school']['email'] or 'N/A'}"
        for detail in application_details
    ])

    message = (
        f"Hello {child.parent.forename},\n\n"
        f"Your application for your child {child.name} has been successfully submitted.\n\n"
        f"Details:\n{details}\n\n"
        "Best Regards,\n"
        "Your School Admission Team"
    )

    recipient_list = [child.parent.email]

    send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)


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

            # Find matching sibling data for the current preference using preference_value
            siblings_for_preference = []
            for sibling_info in sibling_data:
                if sibling_info['preference_value'] == str(index + 1):
                    siblings_for_preference = sibling_info['siblings']

            print(
                f"Adding preference for child {child_id} at school {school.name} with preference {index + 1} and siblings {siblings_for_preference}")

            all_preferences.append({
                'school': {
                    'id': school.id,  # Add school ID here
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
        # Send email notification
        send_application_email(child, all_preferences)
        print(application)

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
            {'status': 'submitted', 'label': 'Application Submitted',
             'is_active': application.status in ['submitted', 'in_progress', 'offer_received', 'offer_accepted']},
            {'status': 'in_progress', 'label': 'In Process',
             'is_active': application.status in ['in_progress', 'offer_received', 'offer_accepted']},
            {'status': 'offer_received', 'label': 'Offer Received',
             'is_active': application.status in ['offer_received', 'offer_accepted']},
            {'status': 'offer_accepted', 'label': 'Offer Accepted',
             'is_active': application.status == 'offer_accepted'},
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


@require_http_methods(["GET"])
def view_application_details(request, application_id):

    try:
        application = get_object_or_404(Application, id=application_id)
        print(application)
        offered_school = application.offered_school
        data = {
            'application_id': application.id,
            'child_name': application.child.name,
            'child_dob': application.child.dob.strftime('%Y-%m-%d'),
            'child_age': calculate_age(application.child.dob),
            'child_nhs_number': application.child.nhs_number,
            'child_gender': application.child.gender,
            'parent_name': f"{application.child.parent.forename} {application.child.parent.surname}",
            'parent_email': application.child.parent.email,
            'parent_phone': application.child.parent.mobile_phone,
            'applied_on': application.applied_on.strftime('%B %d, %Y, %I:%M %p'),
            'status': application.status,
            'preferences': application.preferences,
            'offered_school_id': offered_school.id if offered_school else None,
            'offered_school_name': offered_school.name if offered_school else None,
        }
        print("Sending data to frontend:", data)  # Debugging line
        return JsonResponse(data)
    except Exception as e:
        print("Error:", e)  # Debugging line
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
def edit_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    new_status = request.POST.get('status')
    application.status = new_status

    if new_status == 'offer_received':
        offer_school_id = request.POST.get('offer_school')
        offer_school = get_object_or_404(School, id=offer_school_id)
        application.offered_school = offer_school  # Set the offered_school field
        send_offer_email(application.child, offer_school)  # Send offer email

    application.save()
    return JsonResponse({'success': True})


@require_http_methods(["POST"])
def edit_application_status(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    new_status = request.POST.get('status')
    application.status = new_status
    if application.status == 'offer_accepted':
        send_offer_acceptance_email(application.child, application.offered_school)
    application.save()
    return JsonResponse({'success': True})


def send_offer_acceptance_email(child, offered_school):
    subject = 'Offer Accepted'

    message = (
        f"Hello {child.parent.forename},\n\n"
        f"Congratulations! Your child {child.name} has Accepted an offer.\n\n"
        f"Offered School Details:\n"
        f"School Name: {offered_school.name}\n"
        f"Address: {offered_school.address}\n"
        f"Latitude: {offered_school.latitude}\n"
        f"Longitude: {offered_school.longitude}\n"
        f"Distance: {offered_school.distance} meters\n"
        f"Phone: {offered_school.phone}\n"
        f"Website: {offered_school.website}\n"
        f"Email: {offered_school.email or 'N/A'}\n\n"
        "Best Regards,\n"
        "Your School Admission Team"
    )

    recipient_list = [child.parent.email]

    send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)


def send_offer_email(child, offered_school):
    subject = 'Offer Received'

    message = (
        f"Hello {child.parent.forename},\n\n"
        f"Congratulations! Your child {child.name} has received an offer.\n\n"
        f"Offered School Details:\n"
        f"School Name: {offered_school.name}\n"
        f"Address: {offered_school.address}\n"
        f"Latitude: {offered_school.latitude}\n"
        f"Longitude: {offered_school.longitude}\n"
        f"Distance: {offered_school.distance} meters\n"
        f"Phone: {offered_school.phone}\n"
        f"Website: {offered_school.website}\n"
        f"Email: {offered_school.email or 'N/A'}\n\n"
        "Best Regards,\n"
        "Your School Admission Team"
    )

    recipient_list = [child.parent.email]

    send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)


@login_required
def delete_application(request, application_id):
    application = get_object_or_404(Application, id=application_id)
    child_id = application.child.id
    application.delete()
    return redirect('dashboard')


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
    return redirect('/')


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


# @login_required
# def view_application_details(request, application_id):
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
#         'status': application.status,
#     }
#
#     return JsonResponse(response_data)

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
    extracted_data = None

    if request.method == 'POST':
        form = ManualApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            file = form.cleaned_data['file']
            text = extract_text_from_pdf(file)
            extracted_data = extract_details_from_text(text)
            print(extracted_data)

            # Store the extracted data in the session for further confirmation
            request.session['extracted_data'] = extracted_data

            return redirect('confirm_manual_application')

    else:
        form = ManualApplicationForm()

    return render(request, 'admin/add_manual_application.html', {
        'form': form,
        'extracted_data': extracted_data
    })

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


@login_required
def parent_applications_view(request):
    applications = Application.objects.filter(child__parent=request.user).order_by('-applied_on')
    return render(request, 'parent_applications.html', {'applications': applications})