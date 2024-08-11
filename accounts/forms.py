from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Child, School, Application, Notification


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = (
            'username', 'email', 'password1', 'password2', 'title', 'forename', 'surname', 'sex', 'postcode',
            'home_phone',
            'mobile_phone', 'work_phone')


class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ['name', 'dob', 'gender', 'nhs_number']


class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name', 'address', 'here_place_id', 'latitude', 'longitude', 'phone', 'website', 'email']


class ManualApplicationForm(forms.Form):
    file = forms.FileField(
        label='Upload a file (PDF or Image)',
        help_text='Supported formats: .pdf, .jpg, .jpeg, .png'
    )


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message']
