from django.db import models
from django.contrib.auth.models import AbstractUser


class CustomUser(AbstractUser):
    is_parent = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    title = models.CharField(max_length=10, blank=True)
    forename = models.CharField(max_length=100, blank=True)
    surname = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=10, blank=True)
    postcode = models.CharField(max_length=20, blank=True)
    home_phone = models.CharField(max_length=20, blank=True)
    mobile_phone = models.CharField(max_length=20, blank=True)
    work_phone = models.CharField(max_length=20, blank=True)
    otp = models.CharField(max_length=6, blank=True, null=True)


class Child(models.Model):
    parent = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    dob = models.DateField()
    gender = models.CharField(max_length=100, default="Male")
    nhs_number = models.CharField(max_length=20)

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    here_place_id = models.CharField(max_length=255, unique=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    distance = models.FloatField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.name


class Application(models.Model):
    STATUS_CHOICES = [
        ('submitted', 'Application Submitted'),
        ('in_progress', 'In Progress'),
        ('offer_received', 'Offer Received'),
        ('offer_accepted', 'Offer Accepted'),
    ]

    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    applied_on = models.DateTimeField(auto_now_add=True)
    preferences = models.JSONField(default=list)  # Store all preferences as a JSON list
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    offered_school = models.ForeignKey(School, null=True, blank=True, on_delete=models.SET_NULL,
                                       related_name='applications_offered')

    def __str__(self):
        return f'{self.child.name} - Application'


class Notification(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
