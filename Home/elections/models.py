from django.db import models
from django.utils import timezone
import uuid
from accounts.models import User, Constituency, Assembly, Village


class Party(models.Model):
    name = models.CharField(max_length=150)
    symbol = models.ImageField(upload_to='parties/', null=True, blank=True)

    def __str__(self):
        return self.name


class Election(models.Model):
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
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='village')

    # Location scoping (string-based to match User model)
    constituency = models.CharField(max_length=150, blank=True)
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)

    APPROVAL_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='pending')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'elections'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['level']),
            models.Index(fields=['state', 'district', 'village']),
        ]

    @property
    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.start_time <= now <= self.end_time

    def __str__(self):
        return f"{self.title} ({self.level})"


class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    party = models.CharField(max_length=150, blank=True, null=True)
    symbol = models.CharField(max_length=50, blank=True, null=True)
    photo = models.ImageField(upload_to='candidates/', null=True, blank=True)
    party_photo = models.ImageField(upload_to='candidates/party_photos/', null=True, blank=True)
    party_brochure = models.FileField(upload_to='candidates/brochures/', null=True, blank=True)
    manifesto = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'candidates'

    def __str__(self):
        return f"{self.name} - {self.election.title}"
