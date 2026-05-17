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

from .models import User, OTP, VoterVerification, VoterRoll, VillageAdmin, RegistrationRequest
from .serializers import (
    RegisterSerializer, LoginSerializer, ProfileSerializer,
    OTPVerifySerializer, UserListSerializer, VoterVerificationSerializer,
    VoterRollSerializer, VillageAdminSerializer,
    RegistrationRequestSerializer, RegistrationRequestSubmitSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Register a new user and return JWT tokens."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        from django.core.cache import cache
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Check if email was already verified via progressive OTP flow
        pre_verified = cache.get(f'voter_email_verified_{user.voter_id}')
        if pre_verified and pre_verified.get('email') == user.email:
            user.is_verified = True
            user.save()
            cache.delete(f'voter_email_verified_{user.voter_id}')
            already_verified = True
        else:
            # Fallback: send account OTP
            otp_code = str(random.randint(100000, 999999))
            OTP.objects.create(user=user, code=otp_code,
                               expires_at=timezone.now() + timedelta(minutes=10))
            try:
                send_mail(
                    'SecureVote - Verify Your Account',
                    f'Hello {user.first_name},\n\nYour OTP: {otp_code}\n\nExpires in 10 minutes.\n\n- SecureVote Team',
                    settings.EMAIL_HOST_USER, [user.email], fail_silently=False,
                )
            except Exception as e:
                print(f"Email failed: {e}")
            already_verified = False

        refresh = RefreshToken.for_user(user)
        response_data = {
            'message': 'Registration successful!',
            'already_verified': already_verified,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'voter_id': user.voter_id,
                'role': user.role,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_verified': user.is_verified,
                'village': user.village,
                'district': user.district,
                'state': user.state,
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
        
        if settings.DEBUG and not already_verified:
            response_data['dev_otp'] = otp_code
            print(f"\n{'='*40}\n[DEV MODE] Generated OTP for {user.email}: {otp_code}\n{'='*40}\n")

        return Response(response_data, status=status.HTTP_201_CREATED)


class VoterRollAPIView(APIView):
    """Admin endpoint to list or create VoterRoll entries for their village."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('admin', 'officer'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        qs = VoterRoll.objects.all()
        if request.user.village:
            qs = qs.filter(village=request.user.village, state=request.user.state)
        serializer = VoterRollSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        if request.user.role not in ('admin', 'officer'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        # Auto-fill admin's village/state if not provided
        if not data.get('village') and request.user.village:
            data['village'] = request.user.village
        if not data.get('state') and request.user.state:
            data['state'] = request.user.state
        if not data.get('district') and request.user.district:
            data['district'] = request.user.district
        serializer = VoterRollSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class VoterRollDetailAPIView(APIView):
    """Admin endpoint to view, update, or delete VoterRoll entries."""
    permission_classes = [permissions.IsAuthenticated]

    def _get_roll(self, request, pk):
        if request.user.role not in ('admin', 'officer'):
            return None, Response(status=status.HTTP_403_FORBIDDEN)
        try:
            roll = VoterRoll.objects.get(id=pk)
            if request.user.village and (roll.village != request.user.village or roll.state != request.user.state):
                return None, Response(status=status.HTTP_403_FORBIDDEN)
            return roll, None
        except VoterRoll.DoesNotExist:
            return None, Response(status=status.HTTP_404_NOT_FOUND)

    def get(self, request, pk):
        roll, err = self._get_roll(request, pk)
        if err: return err
        return Response(VoterRollSerializer(roll).data)

    def put(self, request, pk):
        roll, err = self._get_roll(request, pk)
        if err: return err
        serializer = VoterRollSerializer(roll, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, pk):
        return self.put(request, pk)

    def delete(self, request, pk):
        roll, err = self._get_roll(request, pk)
        if err: return err
        roll.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VillageAdminAPIView(APIView):
    """SuperAdmin or equivalent endpoint to list or create VillageAdmins."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('admin', 'officer'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        qs = VillageAdmin.objects.all()
        # You could filter this based on the viewing user's permissions, but for now we return all in their jurisdiction
        if request.user.village:
            qs = qs.filter(village=request.user.village, state=request.user.state)
        serializer = VillageAdminSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        if request.user.role not in ('admin', 'officer'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data.copy()
        
        # Enforce exactly one admin per village
        village = data.get('village')
        district = data.get('district')
        state = data.get('state')
        
        if village and district and state:
            if VillageAdmin.objects.filter(village=village, district=district, state=state).exists():
                return Response(
                    {'detail': 'A Village Admin already exists for this village. Only one admin per village is permitted.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        serializer = VillageAdminSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class VillageAdminDetailAPIView(APIView):
    """Endpoint to delete VillageAdmins."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role not in ('admin', 'officer'):
            return Response(status=status.HTTP_403_FORBIDDEN)
        try:
            admin_entry = VillageAdmin.objects.get(id=pk)
            admin_entry.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except VillageAdmin.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class CheckVoterRollView(APIView):
    """
    Step 1 of registration: validate voter_id + email against the
    local village VoterRoll database before showing the full form.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        voter_id = request.data.get('voter_id', '').strip().upper()
        email = request.data.get('email', '').strip().lower()

        if not voter_id or not email:
            return Response(
                {'error': 'voter_id and email are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            roll = VoterRoll.objects.get(voter_id=voter_id, email=email)
        except VoterRoll.DoesNotExist:
            try:
                roll = VillageAdmin.objects.get(admin_id=voter_id, email=email)
            except VillageAdmin.DoesNotExist:
                return Response({
                    'found': False,
                    'error': 'You are not found in the village database.'
                }, status=status.HTTP_404_NOT_FOUND)

        if roll.is_registered:
            return Response({
                'found': False,
                'error': 'This Voter ID is already registered. Please log in instead.'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Also check if a user account already exists with this voter_id
        if User.objects.filter(voter_id=voter_id).exists():
            return Response({
                'found': False,
                'error': 'An account with this Voter ID already exists. Please log in.'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'found': True,
            'message': 'Voter verified in the local roll! Please complete your registration.',
            'voter_data': {
                'full_name': roll.full_name,
                'village': roll.village,
                'district': roll.district,
                'state': roll.state,
                'nation': roll.nation,
                'mobile_number': roll.mobile_number,
            }
        }, status=status.HTTP_200_OK)


class SendVoterOTPView(APIView):
    """Progressive form Step 2: check voter roll and email an OTP."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.core.cache import cache
        voter_id = request.data.get('voter_id', '').strip().upper()
        email    = request.data.get('email', '').strip().lower()

        if not voter_id or not email:
            return Response({'error': 'voter_id and email are required.'}, status=400)

        try:
            roll = VoterRoll.objects.get(voter_id=voter_id, email=email)
        except VoterRoll.DoesNotExist:
            try:
                roll = VillageAdmin.objects.get(admin_id=voter_id, email=email)
            except VillageAdmin.DoesNotExist:
                return Response({
                    'sent': False,
                    'error': 'You are not found in the village database.'
                }, status=status.HTTP_404_NOT_FOUND)

        if roll.is_registered:
            return Response({'sent': False,
                             'error': 'This Voter ID is already registered. Please log in.'}, status=400)

        cached = cache.get(f'voter_otp_{voter_id}')
        if cached and cached.get('email') == email:
            otp_code = cached['otp']
            cache.set(f'voter_otp_{voter_id}', {'otp': otp_code, 'email': email}, timeout=600)
        else:
            otp_code = str(random.randint(100000, 999999))
            cache.set(f'voter_otp_{voter_id}', {'otp': otp_code, 'email': email}, timeout=600)

        masked = email[:3] + '***@' + email.split('@')[1]
        try:
            send_mail(
                'SecureVote — Email Verification OTP',
                f'Hello {roll.full_name},\n\nYour OTP to verify your email:\n\n  {otp_code}\n\nExpires in 10 minutes.\n\n- SecureVote Team',
                settings.EMAIL_HOST_USER, [email], fail_silently=False,
            )
        except Exception as e:
            print(f"Email error: {e}")
            
        response_data = {
            'sent': True, 
            'masked_email': masked,
            'voter_name': roll.full_name
        }
        
        if settings.DEBUG:
            response_data['dev_otp'] = otp_code
            print(f"\n{'='*40}\n[DEV MODE] Generated OTP for {email}: {otp_code}\n{'='*40}\n")

        return Response(response_data)


class VerifyVoterOTPView(APIView):
    """Progressive form Step 3: verify the emailed OTP, return voter data."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.core.cache import cache
        voter_id = request.data.get('voter_id', '').strip().upper()
        email    = request.data.get('email', '').strip().lower()
        otp      = request.data.get('otp', '').strip()

        cached = cache.get(f'voter_otp_{voter_id}')
        if not cached:
            return Response({'verified': False, 'error': 'OTP expired. Please go back and retry.'}, status=400)
        if cached['otp'] != otp or cached['email'] != email:
            return Response({'verified': False, 'error': 'Incorrect OTP. Try again.'}, status=400)

        cache.delete(f'voter_otp_{voter_id}')
        # Mark email as pre-verified for 30 min (used by RegisterView)
        cache.set(f'voter_email_verified_{voter_id}', {'email': email}, timeout=1800)

        try:
            roll = VoterRoll.objects.get(voter_id=voter_id, email=email)
        except VoterRoll.DoesNotExist:
            try:
                roll = VillageAdmin.objects.get(admin_id=voter_id, email=email)
            except VillageAdmin.DoesNotExist:
                return Response({'verified': False, 'error': 'Voter/Admin not found.'}, status=404)

        return Response({
            'verified': True,
            'voter_data': {
                'full_name':     roll.full_name,
                'village':       roll.village,
                'district':      roll.district,
                'state':         roll.state,
                'nation':        roll.nation,
                'mobile_number': roll.mobile_number,
            }
        })


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
                'village': user.village,
                'district': user.district,
                'state': user.state,
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

class RequestPasswordResetView(APIView):
    """Send an OTP to the user's email for password reset."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        if not email:
            return Response({'error': 'Email is required.'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'message': 'If an account exists with this email, an OTP has been sent.'})

        otp_code = str(random.randint(100000, 999999))
        OTP.objects.create(user=user, code=otp_code,
                           expires_at=timezone.now() + timedelta(minutes=10))

        try:
            send_mail(
                'SecureVote - Password Reset OTP',
                f'Hello {user.first_name},\n\nYour OTP for password reset is: {otp_code}\n\nExpires in 10 minutes.\n\n- SecureVote Team',
                settings.EMAIL_HOST_USER, [user.email], fail_silently=False,
            )
        except Exception as e:
            print(f"Email failed: {e}")

        response_data = {'message': 'OTP sent to your email.'}
        if settings.DEBUG:
            response_data['dev_otp'] = otp_code
            print(f"\n{'='*40}\n[DEV MODE] Password Reset OTP for {email}: {otp_code}\n{'='*40}\n")

        return Response(response_data)


class ResetPasswordView(APIView):
    """Verify OTP and set a new password."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        otp_code = request.data.get('otp', '').strip()
        new_password = request.data.get('password', '').strip()

        if not email or not otp_code or not new_password:
            return Response({'error': 'Email, OTP, and new password are required.'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=404)

        otp = OTP.objects.filter(
            user=user, code=otp_code, is_used=False,
            expires_at__gte=timezone.now()
        ).first()

        if not otp:
            return Response({'error': 'Invalid or expired OTP.'}, status=400)

        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=400)

        user.set_password(new_password)
        user.save()
        otp.is_used = True
        otp.save()

        return Response({'message': 'Password reset successful. You can now log in.'})


# ═══════════════════════════════════════════════════════════════════════════
# Chatbot Registration Request Views (Two-Stage Approval)
# ═══════════════════════════════════════════════════════════════════════════

class SubmitRegistrationRequestView(APIView):
    """
    PUBLIC endpoint — called by the login-page chatbot.
    Accepts voter details, runs AI scoring, creates a RegistrationRequest
    with status=pending_village_admin.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .services.ai_verification import compute_genuineness_score

        serializer = RegistrationRequestSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Prevent duplicate pending submissions
        voter_id = data['voter_id']
        existing = RegistrationRequest.objects.filter(
            voter_id=voter_id,
            status__in=['pending_village_admin', 'pending_voter_admin']
        ).first()
        if existing:
            return Response(
                {'error': 'A registration request for this Voter ID is already pending review.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Run AI analysis
        ai_result = compute_genuineness_score(
            voter_id=voter_id,
            aadhaar_last4=data.get('aadhaar_last4', ''),
            full_name=data.get('full_name', ''),
            date_of_birth=data.get('date_of_birth', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            village=data.get('village', ''),
            state=data.get('state', ''),
        )

        reg_req = RegistrationRequest.objects.create(
            voter_id=voter_id,
            aadhaar_last4=data.get('aadhaar_last4', ''),
            full_name=data.get('full_name', ''),
            date_of_birth=data.get('date_of_birth', ''),
            email=data['email'],
            phone=data.get('phone', ''),
            village=data['village'],
            district=data.get('district', ''),
            state=data['state'],
            status='pending_village_admin',
            ai_score=ai_result['score'],
            ai_details=ai_result,
        )

        return Response({
            'success': True,
            'message': 'Your registration request has been submitted! The Village Admin will review it shortly.',
            'request_id': reg_req.id,
            'ai_score': ai_result['score'],
            'ai_label': ai_result['label'],
        }, status=status.HTTP_201_CREATED)


class RegistrationRequestListView(APIView):
    """
    Admin/officer endpoint — returns all requests filtered by status.
    Query param: ?status=pending_village_admin  (or pending_voter_admin / approved / rejected)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role not in ('admin', 'officer') and not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        qs = RegistrationRequest.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Village Admins only see requests for their village
        if request.user.role == 'admin' and request.user.village:
            qs = qs.filter(village=request.user.village, state=request.user.state)

        serializer = RegistrationRequestSerializer(qs, many=True)
        return Response(serializer.data)


class ForwardToVoterAdminView(APIView):
    """
    Village Admin forwards an approved request to the Voter Administrative.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('admin', 'officer') and not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            req = RegistrationRequest.objects.get(pk=pk)
        except RegistrationRequest.DoesNotExist:
            return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if req.status != 'pending_village_admin':
            return Response(
                {'error': f'Cannot forward. Current status: {req.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', '')
        req.status = 'pending_voter_admin'
        req.village_admin_notes = notes
        req.forwarded_at = timezone.now()
        req.save()

        return Response({
            'success': True,
            'message': 'Request forwarded to Voter Administrative for final approval.',
        })


class ApproveRegistrationView(APIView):
    """
    Voter Administrative approves the request:
    - Creates a VoterRoll entry so the citizen can now register online.
    - Marks request as approved.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # Only superadmin / staff level
        if not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            req = RegistrationRequest.objects.get(pk=pk)
        except RegistrationRequest.DoesNotExist:
            return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if req.status != 'pending_voter_admin':
            return Response(
                {'error': f'Cannot approve. Current status: {req.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if already in VoterRoll
        if VoterRoll.objects.filter(voter_id=req.voter_id).exists():
            return Response(
                {'error': 'Voter ID already exists in the Voter Roll.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', '')

        # Create VoterRoll entry — citizen can now register
        VoterRoll.objects.create(
            voter_id=req.voter_id,
            email=req.email,
            mobile_number=req.phone,
            full_name=req.full_name,
            village=req.village,
            district=req.district,
            state=req.state,
            is_registered=False,
            designated_role='voter',
        )

        req.status = 'approved'
        req.voter_admin_notes = notes
        req.resolved_at = timezone.now()
        req.save()

        return Response({
            'success': True,
            'message': f'{req.full_name} has been approved and added to the Voter Roll. They can now register online.',
        })


class RejectRegistrationView(APIView):
    """
    Reject a registration request at any stage.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if request.user.role not in ('admin', 'officer') and not request.user.is_staff:
            return Response(status=status.HTTP_403_FORBIDDEN)

        try:
            req = RegistrationRequest.objects.get(pk=pk)
        except RegistrationRequest.DoesNotExist:
            return Response({'error': 'Request not found.'}, status=status.HTTP_404_NOT_FOUND)

        if req.status in ('approved', 'rejected'):
            return Response(
                {'error': f'Request is already {req.status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', 'No reason provided.')
        # Store notes in the appropriate field based on who is rejecting
        if req.status == 'pending_village_admin':
            req.village_admin_notes = notes
        else:
            req.voter_admin_notes = notes

        req.status = 'rejected'
        req.resolved_at = timezone.now()
        req.save()

        return Response({
            'success': True,
            'message': 'Registration request has been rejected.',
        })
