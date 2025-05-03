from django.db import models
import uuid
from django.conf import settings


class UserActivity(models.Model):
    ACTIVITY_TYPES = (
        ('played_quiz', 'Played Quiz'),
        ('created_quiz', 'Created Quiz'),
        ('viewed_learning', 'Viewed Learning Content'),
        ('created_learning', 'Created Learning Content'),
        ('followed_user', 'Followed User'),
        ('achieved_rank', 'Achieved Rank'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)

    related_quiz = models.ForeignKey(
        'quizapplication.Quiz', # Use string reference to avoid direct import
        null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    related_learning = models.ForeignKey(
        'learningapplication.LearningContent', # Use string reference
        null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    related_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.SET_NULL, related_name='related_activities' # Different related_name
    )
    details = models.JSONField(null=True, blank=True, help_text="Store extra context like score, rank, etc.")


    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = "User Activities"

    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} at {self.timestamp}"