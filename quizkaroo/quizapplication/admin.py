from django.contrib import admin
from .models import Category, Topic, Quiz, Question, Answer, QuizAttempt, QuizReference

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'topic', 'created_at', 'passing_score', 'is_dynamic']
    list_filter = ['topic', 'is_dynamic']
    search_fields = ['title', 'description']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('topic')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'question_type', 'order')
    list_filter = ('quiz', 'question_type')
    search_fields = ['text']

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('question__quiz',)

@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'time_taken', 'passed', 'attempted_at')
    list_filter = ('quiz', 'passed')
    search_fields = ['student__username', 'quiz__title']

@admin.register(QuizReference)
class QuizReferenceAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'content', 'created_by_teacher')
    list_filter = ('created_by_teacher',)
    search_fields = ['content']