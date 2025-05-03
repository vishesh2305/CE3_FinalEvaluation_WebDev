from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings



class User(AbstractUser):
    # Here all the fields for User model are being inherited from Abstract user which is default model for users in django. 

    ROLE_CHOICES = [
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('open', 'Open'),
        ('school', 'Schools')
    ]

    ACTIVITY_CHOICES=[
        ('current', 'Current Active'),
        ('last', 'Last Active'),
    ]

    phone_number = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    activity_status = models.CharField(max_length=10, choices=ACTIVITY_CHOICES, default='current')

    education_bg = models.ManyToManyField('EducationBackground', blank=True ,related_name='users_with_this_bg')
    learning_level = models.OneToOneField('LearningLevel', on_delete=models.CASCADE, null=True, blank=True, related_name='users_with_this_level')
    friends = models.ManyToManyField('self', through='Friendship', symmetrical=False, related_name='friend_of')
    following = models.ManyToManyField(
        'self',
        symmetrical=False, # Crucial: Following is not necessarily mutual
        related_name='followers',
        blank=True
    )

    def __str__(self):
        return self.username
    

class EducationBackground(models.Model):
    user=models.OneToOneField(User, on_delete=models.CASCADE, related_name='education')
    schooling = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    field_of_interests = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Education of {self.user.username}"
    
class LearningLevel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='learning')
    learning_status = models.CharField(max_length=255, blank=True, null=True)
    content_covered = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Learning level of {self.user.username}"
    

class Friendship(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_received')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.from_user} -> {self.to_user} (since {self.created_at})"




# Avatar choices for user to allow to choose their own avatar    
AVATAR_CHOICES = (
    ('avatar1.png', 'Avatar 1'),
    ('avatar2.png', 'Avatar 2'),
    ('avatar3.png', 'Avatar 3'),
    ('default_avatar.png', 'Default Avatar'),
)


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    bio = models.TextField(blank=True)
    avatar_choice = models.CharField(
        max_length=50,
        choices=AVATAR_CHOICES,
        default='default_avatar.png' # Set a default avatar
    )

    def __str__(self):
        return f"{self.user.username}'s Profile"