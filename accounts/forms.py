from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Child


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
