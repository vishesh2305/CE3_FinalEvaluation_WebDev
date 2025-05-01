from django.urls import path, include
from .views import CategoryListView, TopicListView, QuizListView, QuizDetailView, submit_quiz, QuizSearchView, landingpage, profilepage, my_quizzes
from . import views
from django.contrib.auth import views as auth_views  # Import Django's built-in LoginView
from django.contrib.auth.views import LoginView

app_name = 'quizapplication'

urlpatterns = [
    # add templates path.....
    path('', landingpage, name='landingpage'),
    path('category/', CategoryListView.as_view(), name='category_list'),
    path('category/<int:category_id>/', TopicListView.as_view(), name='topic_list'),
    path('topic/<int:topic_id>/', QuizListView.as_view(), name='quiz_list'),
    path('quiz/<int:pk>/', QuizDetailView.as_view(), name='quiz_detail'),
    path('quiz/<int:quiz_id>/submit/', submit_quiz, name='submit_quiz'),
    path('search/', QuizSearchView.as_view(), name='quiz_search'),
    path('profile/', profilepage, name='profilepage'),
    path('my-quizzes/', my_quizzes, name='my_quizzes'),
    path('quiz/<int:quiz_id>/submit/', views.submit_quiz, name='submit_quiz'),  # Duplicate removed
    path('progress/', views.user_progress, name='user_progress'),
    path('review/', views.quiz_review, name='quiz_review'),
    path('user_activity/', views.user_activity, name='user_activity'),
]