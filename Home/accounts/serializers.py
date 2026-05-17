from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OTP, VoterVerification, VoterRoll, VillageAdmin, RegistrationRequest

class VoterRollSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoterRoll
        fields = '__all__'

class VillageAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = VillageAdmin
        fields = '__all__'

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    voter_id = serializers.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password2',
            'first_name', 'last_name', 'phone',
            'voter_id', 'state', 'district', 'village', 'date_of_birth',
        ]

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})

        # --- VoterRoll check ---
        voter_id = data.get('voter_id', '').strip().upper()
        email = data.get('email', '').strip().lower()
        try:
            roll = VoterRoll.objects.get(voter_id=voter_id, email=email)
        except VoterRoll.DoesNotExist:
            try:
                roll = VillageAdmin.objects.get(admin_id=voter_id, email=email)
            except VillageAdmin.DoesNotExist:
                raise serializers.ValidationError({
                    'voter_id': 'You are not a voter. Your Voter ID and Email were not found in the village database.'
                })
        if roll.is_registered:
            raise serializers.ValidationError({
                'voter_id': 'This Voter ID is already registered in the system.'
            })
        self._roll = roll
        data['voter_id'] = voter_id
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        
        # Apply role and permissions from VoterRoll/VillageAdmin
        user.role = getattr(self._roll, 'designated_role', 'voter')
        if user.role == 'admin':
            user.is_staff = True
            user.is_superuser = True
        elif user.role == 'officer':
            user.is_staff = True
            
        user.save()
        # Mark this roll entry as registered
        self._roll.is_registered = True
        self._roll.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid email or password.')
        if not user.is_active:
            raise serializers.ValidationError('Account is disabled.')
        data['user'] = user
        return data


class ProfileSerializer(serializers.ModelSerializer):
    has_face_registered = serializers.SerializerMethodField()
    voted_elections = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone', 'voter_id', 'role', 'state', 'district',
            'village', 'is_verified', 'date_of_birth', 'profile_picture',
            'created_at', 'updated_at', 'has_face_registered', 'voted_elections'
        ]
        read_only_fields = ['id', 'email', 'voter_id', 'role', 'is_verified', 'created_at', 'updated_at', 'has_face_registered', 'voted_elections', 'profile_picture']

    def get_has_face_registered(self, obj):
        if not obj.voter_id:
            return False
        from accounts.services.faiss_service import faiss_service
        return faiss_service.has_face(obj.voter_id)

    def get_voted_elections(self, obj):
        from voting.models import VoteRecord
        records = VoteRecord.objects.filter(user=obj).select_related('election')
        return [
            {
                'id': r.election.id,
                'title': r.election.title,
                'date_voted': r.created_at
            } for r in records
        ]


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class UserListSerializer(serializers.ModelSerializer):
    """Compact serializer for admin user listings."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'voter_id', 'role', 'state', 'is_verified']


class VoterVerificationSerializer(serializers.ModelSerializer):
    """Serializer for submitting voter identity details."""
    dob_on_card = serializers.DateField(required=False, allow_null=True)
    card_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = VoterVerification
        fields = [
            'submitted_voter_id', 'aadhaar_last4', 'full_name_on_card',
            'dob_on_card', 'card_image',
        ]

    def validate_aadhaar_last4(self, value):
        if value and (not value.isdigit() or len(value) != 4):
            raise serializers.ValidationError('Enter exactly 4 digits of your Aadhaar number.')
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        # Update or create verification record
        instance, _ = VoterVerification.objects.update_or_create(
            user=user,
            defaults={**validated_data, 'status': 'pending'},
        )
        # Auto-approve (in production replace with manual admin review)
        instance.approve()
        return instance


class RegistrationRequestSerializer(serializers.ModelSerializer):
    """Full serializer for RegistrationRequest — used by admin views."""

    class Meta:
        model = RegistrationRequest
        fields = '__all__'
        read_only_fields = ['status', 'ai_score', 'ai_details',
                            'created_at', 'updated_at', 'forwarded_at', 'resolved_at']


class RegistrationRequestSubmitSerializer(serializers.Serializer):
    """Serializer for public chatbot submission — no auth required."""
    voter_id      = serializers.CharField(max_length=30)
    aadhaar_last4 = serializers.CharField(max_length=4)
    full_name     = serializers.CharField(max_length=150)
    date_of_birth = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email         = serializers.EmailField()
    phone         = serializers.CharField(max_length=15, required=False, allow_blank=True)
    village       = serializers.CharField(max_length=100)
    district      = serializers.CharField(max_length=100, required=False, allow_blank=True)
    state         = serializers.CharField(max_length=100)

    def validate_aadhaar_last4(self, value):
        if not value.isdigit() or len(value) != 4:
            raise serializers.ValidationError('Must be exactly 4 numeric digits.')
        return value

    def validate_voter_id(self, value):
        return value.strip().upper()
