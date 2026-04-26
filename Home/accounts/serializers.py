from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OTP, VoterVerification


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            'email', 'username', 'password', 'password2',
            'first_name', 'last_name', 'phone',
            'state', 'district', 'village', 'date_of_birth',
        ]

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        # Generate voter_id
        import uuid
        validated_data['voter_id'] = f"VID-{uuid.uuid4().hex[:10].upper()}"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
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
