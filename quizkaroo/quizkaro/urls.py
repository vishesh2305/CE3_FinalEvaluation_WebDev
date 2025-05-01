from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LoginView, LogoutView
from quizapplication import views
from quizapplication.views import landingpage
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),  # Admin panel path
    path('', include('quizapplication.urls')),  # Include URLs from quizapplication
    # path('student/', include('student.urls')),
    path('learnify/', include('learnify.urls')),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='quizapplication:landingpage'), name='logout'),
]