from django.contrib import admin
from .models import Category, Quiz, Question, Answer, QuizAttempt, UserAnswer, QuizChallenge, ChallengeParticipant

admin.site.register(Category)
admin.site.register(Quiz)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(QuizAttempt)
admin.site.register(UserAnswer)
admin.site.register(QuizChallenge)
admin.site.register(ChallengeParticipant)
