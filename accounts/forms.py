from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Child, School, Application


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


class ManualApplicationForm(forms.ModelForm):
    child_id = forms.IntegerField()
    file = forms.FileField(required=False)  # Add this field for file upload

    class Meta:
        model = Application
        fields = ['preferences', 'child_id', 'file']

