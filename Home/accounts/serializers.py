from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, OTP


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
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'phone', 'voter_id', 'role', 'state', 'district',
            'village', 'is_verified', 'date_of_birth',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'email', 'voter_id', 'role', 'is_verified', 'created_at', 'updated_at']


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class UserListSerializer(serializers.ModelSerializer):
    """Compact serializer for admin user listings."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'voter_id', 'role', 'state', 'is_verified']
