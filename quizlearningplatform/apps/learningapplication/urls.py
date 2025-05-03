from django.urls import path
from . import views

urlpatterns = [
    path('', views.learningpage, name="learningpage")
]