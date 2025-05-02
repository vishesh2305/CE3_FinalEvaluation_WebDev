from django.db import models
import uuid
from django.conf import settings

from apps.quizapplication.models import Category


class LearningContent(models.Model):
    CONTENT_TYPE_CHOICES = (
        ('text', 'Text'),
        ('video_url', 'Video URL'),
        ('pdf', 'PDF Document'),
        ('external_link', 'External Link'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)

    content_text = models.TextField(blank=True, null=True, help_text="Use for 'text' content type.")
    content_file = models.FileField(upload_to='learning_files/', blank=True, null=True, help_text="Use for 'pdf' content type.")
    content_url = models.URLField(blank=True, null=True, help_text="Use for 'video_url' or 'external_link' content types.")


    creator = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='created_learning_content', on_delete=models.CASCADE)
    category = models.ForeignKey(Category, related_name='learning_content', on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-created_at']
        verbose_name_plural="Learning Content"

    def __str__(self):
        return f"{self.title} ({self.get_content_type_display()})"