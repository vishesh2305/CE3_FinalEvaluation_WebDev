from django.http import HttpResponseRedirect
from django.urls import reverse
from django.conf import settings

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_paths = [
            reverse('quizapplication:landingpage'),
            reverse('login'),
            reverse('signup'),
            settings.LOGIN_URL,  # Add LOGIN_URL from settings
        ]

        path = request.path_info

        if not request.user.is_authenticated and path not in allowed_paths:
            return HttpResponseRedirect(reverse('login') + '?next=' + path)

        response = self.get_response(request)
        return response