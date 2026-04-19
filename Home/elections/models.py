from django.db import models
from django.conf import settings
import uuid


class Election(models.Model):
    """Election model supporting National, State, and Village levels."""

    LEVEL_CHOICES = (
        ('national', 'National'),
        ('state', 'State'),
        ('village', 'Village'),
    )
    STATUS_CHOICES = (
        ('upcoming', 'Upcoming'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    constituency = models.CharField(max_length=200, blank=True)
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_elections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'elections'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['level', 'status']),
            models.Index(fields=['state', 'district']),
            models.Index(fields=['start_time', 'end_time']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_level_display()})"

    @property
    def is_active(self):
        from django.utils import timezone
        now = timezone.now()
        return self.start_time <= now <= self.end_time


class Candidate(models.Model):
    """Candidate in an election."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    name = models.CharField(max_length=200)
    party = models.CharField(max_length=200)
    symbol = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)
    manifesto = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'candidates'
        ordering = ['name']
        indexes = [
            models.Index(fields=['election']),
        ]

    def __str__(self):
        return f"{self.name} - {self.party} ({self.election.title})"
