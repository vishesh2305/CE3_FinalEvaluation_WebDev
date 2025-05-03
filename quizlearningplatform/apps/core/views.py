from django.shortcuts import render, HttpResponse

# Create your views here.
def home(request):  # Add the 'request' parameter
    return HttpResponse("This is Home Page")