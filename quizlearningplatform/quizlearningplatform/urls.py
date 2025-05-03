from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('users/', include('apps.users.urls')),  # Include users app URLs
    path('quiz/', include('apps.quizapplication.urls')),  # Include quiz app URLs
    path('learning/', include('apps.learningapplication.urls')),  # Include learning app URLs
    path('', include('apps.core.urls')),  # Include core app URLs (or your main app)
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)