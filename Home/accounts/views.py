from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta
import random

from .models import User, OTP
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    OTPVerifySerializer, UserListSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Register a new user and return JWT tokens."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate OTP for verification
        otp_code = str(random.randint(100000, 999999))
        OTP.objects.create(
            user=user,
            code=otp_code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        # Mock: print OTP to console (replace with Twilio/FCM in prod)
        print(f"[MOCK OTP] User: {user.email} | OTP: {otp_code}")

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Registration successful. Please verify your OTP.',
            'otp_sent': True,
            'mock_otp': otp_code,  # Remove in production
            'user': {
                'id': str(user.id),
                'email': user.email,
                'voter_id': user.voter_id,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Authenticate user and return JWT tokens."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Login successful.',
            'user': {
                'id': str(user.id),
                'email': user.email,
                'voter_id': user.voter_id,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_verified': user.is_verified,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })


class OTPVerifyView(APIView):
    """Verify OTP and mark user as verified."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        otp = OTP.objects.filter(
            user=user, code=code, is_used=False,
            expires_at__gte=timezone.now()
        ).first()

        if not otp:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_used = True
        otp.save()
        user.is_verified = True
        user.save()

        return Response({'message': 'Account verified successfully.'})


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the authenticated user's profile."""
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """Admin-only: list all users."""
    serializer_class = UserListSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = User.objects.all().order_by('-created_at')

    def get_queryset(self):
        qs = super().get_queryset()
        role = self.request.query_params.get('role')
        state = self.request.query_params.get('state')
        if role:
            qs = qs.filter(role=role)
        if state:
            qs = qs.filter(state=state)
        return qs


class DashboardStatsView(APIView):
    """Admin-only: dashboard analytics."""
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        from elections.models import Election
        from voting.models import Vote

        total_users = User.objects.count()
        verified_users = User.objects.filter(is_verified=True).count()
        total_elections = Election.objects.count()
        active_elections = Election.objects.filter(
            start_time__lte=timezone.now(),
            end_time__gte=timezone.now()
        ).count()
        total_votes = Vote.objects.count()

        return Response({
            'total_users': total_users,
            'verified_users': verified_users,
            'total_elections': total_elections,
            'active_elections': active_elections,
            'total_votes': total_votes,
        })
