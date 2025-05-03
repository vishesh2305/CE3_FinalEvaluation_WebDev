from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),  # Assuming you have a view named 'home' in apps/core/views.py
]