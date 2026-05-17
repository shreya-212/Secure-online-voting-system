from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

# ─── Location Hierarchy ───

class Constituency(models.Model):
    name = models.CharField(max_length=150)
    state = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.state})"

class Assembly(models.Model):
    name = models.CharField(max_length=150)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='assemblies')

    def __str__(self):
        return f"{self.name} - {self.constituency.name}"

class Village(models.Model):
    name = models.CharField(max_length=150)
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE, related_name='villages')

    def __str__(self):
        return f"{self.name} - {self.assembly.name}"

class Booth(models.Model):
    name = models.CharField(max_length=150)
    village = models.ForeignKey(Village, on_delete=models.CASCADE, related_name='booths')

    def __str__(self):
        return f"{self.name} ({self.village.name})"

# ─── Voter / Admin Rolls ───

class VoterRoll(models.Model):
    """
    Local village voter roll — pre-populated by election officers.
    A citizen can only register if their voter_id + email exist here.
    """
    voter_id = models.CharField(max_length=30, unique=True)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15, blank=True)
    full_name = models.CharField(max_length=150)
    village = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100)
    nation = models.CharField(max_length=100, default='India')
    date_of_birth = models.DateField(null=True, blank=True)
    is_registered = models.BooleanField(
        default=False,
        help_text='Becomes True once the voter completes online registration.'
    )
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('officer', 'Election Officer'),
        ('voter', 'Voter'),
    )
    designated_role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='voter',
        help_text='If set to Admin, the user automatically becomes the Village Admin upon registration.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'voter_rolls'
        indexes = [
            models.Index(fields=['voter_id']),
            models.Index(fields=['email']),
            models.Index(fields=['village', 'state']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.voter_id}) — {self.village}, {self.state}"


class VillageAdmin(models.Model):
    """
    Dedicated table for Village Admins to avoid mixing them with VoterRoll.
    Functionality matches VoterRoll but strictly for administrative roles.
    """
    admin_id = models.CharField(max_length=30, unique=True, verbose_name="Admin ID")
    email = models.EmailField()
    mobile_number = models.CharField(max_length=15, blank=True)
    full_name = models.CharField(max_length=150)
    village = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100)
    nation = models.CharField(max_length=100, default='India')
    date_of_birth = models.DateField(null=True, blank=True)
    is_registered = models.BooleanField(
        default=False,
        help_text='Becomes True once the admin completes online registration.'
    )
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('officer', 'Election Officer'),
    )
    designated_role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='admin',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'village_admins'
        indexes = [
            models.Index(fields=['admin_id']),
            models.Index(fields=['email']),
            models.Index(fields=['village', 'state']),
        ]

    def __str__(self):
        return f"Admin: {self.full_name} ({self.admin_id}) — {self.village}, {self.state}"

# ─── Custom User Model ───

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
    voter_id = models.CharField(max_length=30, unique=True, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='voter')
    state = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    village = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    face_encoding = models.BinaryField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Location hierarchy FK references (optional, for election scoping)
    booth = models.ForeignKey(Booth, on_delete=models.SET_NULL, null=True, blank=True)
    village_ref = models.ForeignKey(Village, on_delete=models.SET_NULL, null=True, blank=True, related_name='users')
    assembly = models.ForeignKey(Assembly, on_delete=models.SET_NULL, null=True, blank=True)
    constituency = models.ForeignKey(Constituency, on_delete=models.SET_NULL, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    # To resolve reverse accessor conflicts with Django's default User model:
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set_v2',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set_v2',
        blank=True,
    )

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


# ─── Chatbot Registration Request (Two-Stage Approval) ───

class RegistrationRequest(models.Model):
    """
    Voter registration request submitted via the login-page chatbot.
    Flows through two approval stages:
      pending_village_admin → pending_voter_admin → approved / rejected
    """

    STATUS_CHOICES = (
        ('pending_village_admin', 'Pending Village Admin'),
        ('pending_voter_admin',   'Pending Voter Administrative'),
        ('approved',              'Approved'),
        ('rejected',              'Rejected'),
    )

    # Submitted by the citizen
    voter_id       = models.CharField(max_length=30)
    aadhaar_last4  = models.CharField(max_length=4, help_text='Last 4 digits of Aadhaar')
    full_name      = models.CharField(max_length=150)
    date_of_birth  = models.CharField(max_length=20, blank=True)   # stored as string from chatbot
    email          = models.EmailField()
    phone          = models.CharField(max_length=15, blank=True)
    village        = models.CharField(max_length=100)
    district       = models.CharField(max_length=100, blank=True)
    state          = models.CharField(max_length=100)

    # Workflow
    status         = models.CharField(max_length=30, choices=STATUS_CHOICES,
                                      default='pending_village_admin')

    # AI analysis
    ai_score       = models.IntegerField(default=0, help_text='Genuineness score 0-100')
    ai_details     = models.JSONField(default=dict, help_text='Breakdown of AI checks')

    # Admin notes
    village_admin_notes = models.TextField(blank=True)
    voter_admin_notes   = models.TextField(blank=True)

    # Timestamps
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)
    forwarded_at   = models.DateTimeField(null=True, blank=True)
    resolved_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'registration_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['voter_id']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"RegRequest: {self.full_name} ({self.voter_id}) — {self.status}"
