from django.db import models
from django.conf import settings
import uuid


class Notification(models.Model):
    """User notification for vote confirmations, reminders, results."""

    TYPE_CHOICES = (
        ('vote_confirm', 'Vote Confirmation'),
        ('election_reminder', 'Election Reminder'),
        ('results', 'Election Results'),
        ('general', 'General'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.title} → {self.user.email}"
