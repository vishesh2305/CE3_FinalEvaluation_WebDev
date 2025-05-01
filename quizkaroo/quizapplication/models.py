from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name

class Topic(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, related_name='topics', on_delete=models.CASCADE)

    def __str__(self):
        return self.name

class Quiz(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    topic = models.ForeignKey(Topic, related_name='quizzes', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    passing_score = models.PositiveIntegerField(default=50)
    is_dynamic = models.BooleanField(default=False)

    def __str__(self):
        return self.title

class Question(models.Model):
    SINGLE_CHOICE = 'SC'
    MULTI_CHOICE = 'MC'
    QUESTION_TYPE_CHOICES = [
        (SINGLE_CHOICE, 'Single Choice'),
        (MULTI_CHOICE, 'Multiple Choice'),
    ]

    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    question_type = models.CharField(max_length=2, choices=QUESTION_TYPE_CHOICES, default=SINGLE_CHOICE)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class QuizAttempt(models.Model):
    student = models.ForeignKey(User, related_name='quiz_attempts', on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, related_name='attempts', on_delete=models.CASCADE)
    score = models.PositiveIntegerField()
    time_taken = models.DurationField()
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.student.username} - {self.quiz.title} - {self.score}/{self.quiz.questions.count()}'

class QuizReference(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='references', on_delete=models.CASCADE)
    content = models.TextField()
    created_by_teacher = models.BooleanField(default=False)

    def __str__(self):
        return f'Reference for {self.quiz.title}'

class QuizResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    quiz_name = models.CharField(max_length=255)
    score = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Guest'} - {self.quiz_name} - {self.score}"

class UserQuizActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)
    completion_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'quiz')

    def __str__(self):
        return f"{self.user.username} - {self.quiz.title}"