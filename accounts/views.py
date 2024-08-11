from io import BytesIO

from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.crypto import get_random_string
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from .forms import CustomUserCreationForm, ChildForm, SchoolForm, ManualApplicationForm, NotificationForm
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
from django.db.models import Count

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
from collections import defaultdict

def admin_dashboard(request):
    # Basic Counts
    total_applications = Application.objects.count()
    total_children = Child.objects.count()
    total_applications_in_progress = Application.objects.filter(status='in_progress').count()
    total_offers_accepted = Application.objects.filter(status='offer_accepted').count()

    # Applications by Status
    submitted_count = Application.objects.filter(status='submitted').count()
    in_progress_count = Application.objects.filter(status='in_progress').count()
    offer_received_count = Application.objects.filter(status='offer_received').count()
    offer_accepted_count = Application.objects.filter(status='offer_accepted').count()

    # Applications Over Time
    applications_over_time = (
        Application.objects
        .extra(select={'day': 'date(applied_on)'})
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    applications_over_time_dates = [entry['day'] for entry in applications_over_time]
    applications_over_time_counts = [entry['count'] for entry in applications_over_time]

    # Gender Distribution
    male_count = Child.objects.filter(gender='Male').count()
    female_count = Child.objects.filter(gender='Female').count()

    # Age Distribution
    children = Child.objects.all()
    age_distribution = {}
    for child in children:
        age = calculate_age(child.dob)
        if age not in age_distribution:
            age_distribution[age] = 0
        age_distribution[age] += 1
    age_distribution_labels = list(age_distribution.keys())
    age_distribution_counts = list(age_distribution.values())

    # School Preference Trends
    school_preference_counts = defaultdict(int)
    applications = Application.objects.all()

    for application in applications:
        preferences = application.preferences
        for preference in preferences:
            school_id = preference['school']['id']
            school_preference_counts[school_id] += 1

    total_preferences = sum(school_preference_counts.values())
    school_preference_data = []

    for school_id, count in school_preference_counts.items():
        school = School.objects.get(id=school_id)
        percentage = (count / total_preferences) * 100
        school_preference_data.append({
            'name': school.name,
            'count': count,
            'percentage': round(percentage, 2),
        })

    # Sort the school preference data by count in descending order
    school_preference_data.sort(key=lambda x: x['count'], reverse=True)

    context = {
        'total_applications': total_applications,
        'total_children': total_children,
        'total_applications_in_progress': total_applications_in_progress,
        'total_offers_accepted': total_offers_accepted,
        'submitted_count': submitted_count,
        'in_progress_count': in_progress_count,
        'offer_received_count': offer_received_count,
        'offer_accepted_count': offer_accepted_count,
        'applications_over_time_dates': applications_over_time_dates,
        'applications_over_time_counts': applications_over_time_counts,
        'male_count': male_count,
        'female_count': female_count,
        'age_distribution_labels': age_distribution_labels,
        'age_distribution_counts': age_distribution_counts,
        'school_preference_data': school_preference_data,  # Pass the combined data as a list of dicts
    }

    return render(request, 'admin/admin_dashboard.html', context)

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

            # Redirect back to the same page to display the modal with extracted data
            return redirect('add_manual_application')

    else:
        form = ManualApplicationForm()
        extracted_data = request.session.get('extracted_data', None)  # Retrieve extracted data from the session

    return render(request, 'admin/add_manual_application.html', {
        'form': form,
        'extracted_data': extracted_data  # Pass extracted data to the template
    })

def generate_unique_child_id():
    last_child = Child.objects.order_by('id').last()
    if last_child:
        return last_child.id + 1
    else:
        return 1


@login_required
@user_passes_test(is_admin)
def confirm_manual_application(request):
    # Extract data from session
    extracted_data = request.session.get('extracted_data')

    if not extracted_data:
        return redirect('add_manual_application')

    child_data = {
        'name': extracted_data['child_name'],
        'dob': extracted_data['child_dob'],
        'gender': extracted_data['child_gender'],
        'nhs_number': extracted_data['child_nhs'],
    }

    parent_data = {
        'email': extracted_data['parent_email'],
        'title': extracted_data['parent_title'],
        'forename': extracted_data['parent_forename'],
        'surname': extracted_data['parent_surname'],
        'sex': extracted_data['parent_sex'],
        'address': extracted_data['parent_address'],
        'phone': extracted_data['parent_phone'],
    }

    preferences = extracted_data['preferences']

    # Store child_data, parent_data, and preferences in session to access later
    request.session['child_data'] = child_data
    request.session['parent_data'] = parent_data
    request.session['preferences'] = preferences
    request.session['child_id'] = generate_unique_child_id()

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
            return redirect(reverse('admin_dashboard'))  # Redirect to the admin dashboard
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


def admin_manage_children(request):
    if not request.user.is_superuser:
        return redirect('login')  # or wherever you'd like to redirect non-admins

    children = Child.objects.all()
    context = {
        'children': children
    }
    return render(request, 'admin/admin_manage_children.html', context)


# Notifications View
from django.http import JsonResponse
from django.template.loader import render_to_string

@login_required
@user_passes_test(is_admin)
def notification_list(request):
    notifications = Notification.objects.all().order_by('-date')
    return render(request, 'admin/notification_list.html', {'notifications': notifications})
@login_required
@user_passes_test(is_admin)
def notification_create(request):
    if request.method == 'POST':
        form = NotificationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('notification_list')  # Redirect to the notification list after saving
    else:
        form = NotificationForm()  # Initialize an empty form for GET requests

    return render(request, 'admin/notification_form.html', {'form': form})
@login_required
@user_passes_test(is_admin)
def notification_update(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    if request.method == 'POST':
        form = NotificationForm(request.POST, instance=notification)
        if form.is_valid():
            form.save()
            return redirect('notification_list')  # Redirect to the list after saving the update
    else:
        form = NotificationForm(instance=notification)  # Prepopulate the form with the existing notification data

    return render(request, 'admin/notification_form.html', {'form': form})
@login_required
@user_passes_test(is_admin)
def notification_delete(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    if request.method == 'POST':
        notification.delete()
        return redirect('notification_list')  # Redirect to the list after deletion

    return render(request, 'admin/notification_confirm_delete.html', {'notification': notification})