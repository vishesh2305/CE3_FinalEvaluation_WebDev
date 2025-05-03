from django.db import models
import uuid
from django.conf import settings
from django.utils import timezone
from django.db.models import UniqueConstraint


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural="Categories"

    def __str__(self):
        return self.name
    

class Quiz(models.Model):
    DIFFICULTY_CHOICES = (
        ('Easy', 'Easy'),
        ('Medium', 'Medium'),
        ('Hard', 'Hard'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # UUID primary key
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, related_name='quizzes', on_delete=models.SET_NULL, null=True, blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_quizzes', on_delete=models.CASCADE)
    difficulty_level = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='Medium')
    time_limit = models.DurationField(null=True, blank=True, help_text="Optional: Duration in HH:MM:SS format") # Or use IntegerField for seconds
    is_published = models.BooleanField(default=False, help_text="Whether the quiz is visible to others (for user-created quizzes)")
    is_inbuilt = models.BooleanField(default=False, help_text="Is this a pre-loaded quiz managed by admin?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name_plural="Quizzes"
        ordering = ['-created_at']
    def __str__(self):
        return self.title
    


class Question(models.Model):
    QUESTION_TYPE_CHOICES = (
        ('MCQ', 'Multiple Choice'),
        ('TF', 'True/False'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    question_type = models.CharField(max_length=5, choices=QUESTION_TYPE_CHOICES, default='MCQ')
    marks = models.PositiveIntegerField(default=1)
    explanation = models.TextField(blank=True, null=True, help_text="Explanation shown after quiz completion") # User Req 14 support
    order = models.PositiveIntegerField(default=0, help_text="Order of question in the quiz (if not shuffled)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering= ['order', 'created_at']

    def __str__(self):
        return f"{self.quiz.title} - Q {self.order}: {self.text[:50]}..."
    

class Answer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.question.text[:30]}... - Ans: {self.text[:30]}... ({'Correct' if self.is_correct else 'Incorrect'})"
    



class QuizAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='quiz_attempts', on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, related_name='attempts', on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Score achieved by the user, calculated after completion.")
    completed = models.BooleanField(default=False, help_text="Indicates if the quiz attempt has been completed.")
    start_time = models.DateTimeField(auto_now_add=True, help_text="Timestamp when the user started the quiz.")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the user submitted or finished the quiz.")

    class Meta:
        ordering = ['-start_time']


    def __str__(self):
        return f"{self.user.username}'s attempt on {self.quiz.title}"
    
    def calculate_score(self):
        pass






class UserAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(QuizAttempt, related_name='user_answers', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name='user_answers', on_delete=models.CASCADE)
    selected_answers = models.ManyToManyField(Answer, related_name='user_selections', blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        unique_together = ('attempt', 'question')

    def __str__(self):
        selected_texts = ", ".join([ans.text for ans in self.selected_answers.all()])
        return f"Answer by {self.attempt.user.username} for Q: {self.question.text[:30]}... in Attempt {self.attempt.id}"
    
    def check_correctness(self):
        correct_answers = set(self.question.answers.filter(is_correct=True))
        selected_answers_set = set(self.selected_answers.all())
        return correct_answers == selected_answers_set
    



class QuizChallenge(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # Unique ID for joining
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='challenges')
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_challenges')
    start_time = models.DateTimeField(help_text="Scheduled start time for the challenge")
    end_time = models.DateTimeField(help_text="Scheduled end time for the challenge")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    max_players = models.PositiveIntegerField(null=True, blank=True, help_text="Optional limit on the number of participants")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_time']

    def __str__(self):
        return f"Challenge for '{self.quiz.title}' by {self.creator.username}"
    


class ChallengeParticipant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    challenge = models.ForeignKey(QuizChallenge, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='challenge_participations')
    join_time = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(null=True, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['challenge', '-score', 'join_time'] # Order by challenge, then score (desc), then join time
        constraints = [
            UniqueConstraint(fields=['challenge', 'user'], name='unique_participant_per_challenge')
        ]

    def __str__(self):
        return f"{self.user.username} participating in {self.challenge.id}"
    


