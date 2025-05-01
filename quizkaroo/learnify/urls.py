from django.urls import path
from . import views

app_name = 'learnify'

urlpatterns = [
    path('', views.search_topic, name='search_topic'),
    path('result/', views.show_result, name='show_result'),
    path('learn-more/', views.learn_more, name='learn_more'),
    path('create-quiz/', views.create_quiz, name='create_quiz'),
]
