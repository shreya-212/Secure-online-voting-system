from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from datetime import timedelta
import random
import re
import io
import traceback
from django.core.mail import send_mail
from django.conf import settings

from .models import User, OTP, VoterVerification
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    OTPVerifySerializer, UserListSerializer, VoterVerificationSerializer,
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
        # Send actual OTP via Email
        subject = 'SecureVote - Verify Your Account'
        message = f'Hello {user.first_name},\n\nYour OTP for verifying your SecureVote account is: {otp_code}\n\nThis OTP will expire in 10 minutes.\n\nThank you,\nSecureVote Team'
        
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
            print(f"OTP sent successfully to {user.email}")
        except Exception as e:
            print(f"Failed to send email to {user.email}: {str(e)}")

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


def _extract_voter_card_data(image_bytes):
    """Run OCR on a voter card image and extract key fields using regex."""
    try:
        import pytesseract
        from PIL import Image
        from django.conf import settings

        tesseract_cmd = getattr(settings, 'TESSERACT_CMD', None)
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        img = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(img, lang='eng')
    except ImportError:
        return {'error': 'OCR service is not available. Please use the "Enter Manually" tab to input your Voter ID details instead.'}
    except Exception as e:
        error_msg = str(e)
        if 'tesseract is not installed' in error_msg.lower() or 'not found' in error_msg.lower():
            return {'error': 'OCR service (Tesseract) is not installed on this server. Please use the "Enter Manually" tab to input your Voter ID details instead.'}
        return {'error': f'OCR failed: {error_msg}'}

    # Helper: clean and extract
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    full_text = ' '.join(lines)

    # Voter ID pattern: typically like ABC1234567 or VID-XXXXXXXX
    voter_id_match = re.search(r'\b([A-Z]{3}[0-9]{7}|VID-[A-Z0-9]{8,})\b', full_text)
    voter_id = voter_id_match.group(1) if voter_id_match else ''

    # Date of birth: DD/MM/YYYY or DD-MM-YYYY
    dob_match = re.search(r'\b(\d{2}[\/\-]\d{2}[\/\-]\d{4})\b', full_text)
    dob_raw = dob_match.group(1) if dob_match else ''
    dob_iso = ''
    if dob_raw:
        parts = re.split(r'[\/\-]', dob_raw)
        if len(parts) == 3:
            dob_iso = f"{parts[2]}-{parts[1]}-{parts[0]}"  # YYYY-MM-DD

    # Name: look for "Name:" label or pick longest capitalised line
    name = ''
    name_match = re.search(r'(?:Name|ELECTOR\'?S? NAME)[:\s]+([A-Z][A-Za-z\s]+)', full_text)
    if name_match:
        name = name_match.group(1).strip()
    else:
        caps_lines = [l for l in lines if l.isupper() and len(l) > 5]
        if caps_lines:
            name = caps_lines[0].title()

    return {
        'voter_id': voter_id,
        'name': name,
        'dob': dob_iso,
        'raw_text': text[:500],  # Return snippet for debugging
    }


class ExtractCardView(APIView):
    """Extract voter details from an uploaded voter card image via OCR."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        image_file = request.FILES.get('card_image')
        if not image_file:
            return Response({'error': 'No image file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        image_bytes = image_file.read()
        result = _extract_voter_card_data(image_bytes)

        if 'error' in result:
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        return Response({
            'extracted': result,
            'message': 'Text extracted. Please review and confirm your details.',
        })


class VoterVerifyIdentityView(APIView):
    """Submit voter identity for verification (manual or post-OCR confirm)."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.is_verified:
            return Response({'message': 'Your identity is already verified.'})

        serializer = VoterVerificationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'message': 'Identity verified successfully!',
            'is_verified': True,
            'voter_id': user.voter_id,
        })


from .services.faiss_service import faiss_service

class RegisterFaceView(APIView):
    """Registers a LIVE webcam face into the FAISS index mapped to the user ID."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not user.voter_id:
            return Response({'error': 'You must be registered as a voter first.'}, status=400)

        image_file = request.FILES.get('live_image')
        if not image_file:
            return Response({'error': 'No image file provided.'}, status=400)

        try:
            image_bytes = image_file.read()
            # Register in FAISS
            faiss_service.register_face(user.voter_id, image_bytes)
            
            # Save as profile picture if not set
            if not user.profile_picture:
                image_file.seek(0)
                user.profile_picture.save(f"profile_{user.id}.jpg", image_file)
                user.save()
                
            return Response({'message': 'Face successfully registered.'})
        except ValueError as e:
            return Response({'error': str(e)}, status=422)
        except Exception as e:
            traceback.print_exc()
            return Response({'error': f'Registration failed: {str(e)}'}, status=500)


class VerifyFaceView(APIView):
    """Verifies a LIVE webcam face against the FAISS index to authenticate voter_id.
    
    SECURITY: voter_id is ALWAYS taken from the authenticated user's server-side
    profile, NOT from client input. This prevents spoofing.
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        # SECURITY: Always use the server-side voter_id, never trust client input
        voter_id = user.voter_id
        if not voter_id:
            return Response({'error': 'You must be registered as a voter first.'}, status=400)

        image_file = request.FILES.get('live_image')
        if not image_file:
            return Response({'error': 'No image file provided.'}, status=400)

        try:
            image_bytes = image_file.read()
            result = faiss_service.verify_face(voter_id, image_bytes)
            
            if result.get('verified'):
                return Response(result)
            return Response(result, status=401)
            
        except ValueError as e:
            return Response({'error': str(e)}, status=422)
        except Exception as e:
            traceback.print_exc()
            return Response({'error': f'Verification failed: {str(e)}'}, status=500)

