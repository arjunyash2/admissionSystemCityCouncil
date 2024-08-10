from .models import Notification

def notifications_processor(request):
    notifications = Notification.objects.all().order_by('-date')
    return {'notifications': notifications}
