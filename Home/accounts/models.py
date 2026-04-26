from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    """Custom user model with voter-specific fields and role support."""

    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('officer', 'Election Officer'),
        ('voter', 'Voter'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    voter_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='voter')
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['state', 'district', 'village']),
            models.Index(fields=['voter_id']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class OTP(models.Model):
    """One-time password for phone/email verification."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'otps'
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.user.email} - {self.code}"


class VoterVerification(models.Model):
    """Stores voter identity verification submission per user."""

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='voter_verification')
    submitted_voter_id = models.CharField(max_length=30, blank=True)
    aadhaar_last4 = models.CharField(max_length=4, blank=True, help_text='Last 4 digits only')
    full_name_on_card = models.CharField(max_length=150, blank=True)
    dob_on_card = models.DateField(null=True, blank=True)
    card_image = models.ImageField(upload_to='voter_cards/', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'voter_verifications'

    def __str__(self):
        return f"Verification for {self.user.email} — {self.status}"

    def approve(self):
        """Approve verification and mark user as verified."""
        self.status = 'approved'
        self.save()
        self.user.is_verified = True
        if self.submitted_voter_id:
            self.user.voter_id = self.submitted_voter_id
        self.user.save()
