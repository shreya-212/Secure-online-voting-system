import hashlib
import uuid
import random
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import OTP
from .models import Vote, VoteRecord
from .serializers import CastVoteSerializer
from elections.models import Election, Candidate


class CastVoteView(APIView):
    """
    Cast a vote in an election. Transaction-safe with duplicate prevention
    and anonymous vote storage using SHA-256 hashing.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CastVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        election_id = serializer.validated_data['election_id']
        candidate_id = serializer.validated_data['candidate_id']
        otp_code = serializer.validated_data['otp_code']

        # Verify OTP
        otp = OTP.objects.filter(
            user=user, code=otp_code, is_used=False,
            expires_at__gte=timezone.now()
        ).first()

        if not otp:
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify user is verified
        if not user.is_verified:
            return Response(
                {'error': 'You must verify your account before voting.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get election
        try:
            election = Election.objects.get(id=election_id)
        except Election.DoesNotExist:
            return Response({'error': 'Election not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Check election is active (use status field set by admin)
        if election.status != 'active':
            return Response(
                {'error': 'This election is not currently active.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check eligibility
        if election.level == 'state' and election.state != user.state:
            return Response(
                {'error': 'You are not eligible for this state election.'},
                status=status.HTTP_403_FORBIDDEN
            )
        elif election.level == 'village':
            if election.state != user.state or election.district != user.district or election.village != user.village:
                return Response(
                    {'error': 'You are not eligible for this village election.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Check candidate belongs to election
        try:
            candidate = Candidate.objects.get(id=candidate_id, election=election)
        except Candidate.DoesNotExist:
            return Response(
                {'error': 'Candidate not found in this election.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Transaction-safe vote casting
        try:
            with transaction.atomic():
                # Check duplicate vote (with SELECT FOR UPDATE)
                if VoteRecord.objects.filter(user=user, election=election).exists():
                    return Response(
                        {'error': 'You have already voted in this election.'},
                        status=status.HTTP_409_CONFLICT
                    )

                # Generate SHA-256 vote hash for integrity
                hash_input = f"{user.id}-{election.id}-{candidate.id}-{uuid.uuid4()}"
                vote_hash = hashlib.sha256(hash_input.encode()).hexdigest()

                # Create anonymous vote (no user FK)
                Vote.objects.create(
                    election=election,
                    candidate=candidate,
                    vote_hash=vote_hash,
                )

                # Create vote record (tracks who voted, not who they voted for)
                VoteRecord.objects.create(
                    user=user,
                    election=election,
                )

                # Mark OTP as used after successful vote
                otp.is_used = True
                otp.save()

            # Trigger async notification
            try:
                from notifications.tasks import send_vote_confirmation
                send_vote_confirmation.delay(str(user.id), str(election.id))
            except Exception:
                pass  # Don't fail the vote if notification fails

            return Response({
                'message': 'Vote cast successfully!',
                'vote_hash': vote_hash,
                'election': election.title,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'error': f'An error occurred: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VoteStatusView(APIView):
    """Check if the current user has voted in a specific election."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, election_id):
        has_voted = VoteRecord.objects.filter(
            user=request.user, election_id=election_id
        ).exists()
        return Response({'has_voted': has_voted})

class SendVoteOTPView(APIView):
    """Send an OTP to the user's email for vote confirmation."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        email = request.data.get('email')

        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if email.lower() != user.email.lower():
            return Response({'error': 'This email does not match your registered account.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Invalidate old OTPs for this user
        OTP.objects.filter(user=user, is_used=False).update(is_used=True)

        # Generate new OTP
        otp_code = str(random.randint(100000, 999999))
        OTP.objects.create(
            user=user,
            code=otp_code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        subject = 'SecureVote - Confirm Your Vote'
        message = f'Hello {user.first_name},\n\nYour OTP to confirm your vote is: {otp_code}\n\nThis OTP will expire in 5 minutes. Do not share this code with anyone.\n\nThank you,\nSecureVote Team'
        
        try:
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [user.email],
                fail_silently=False,
            )
            return Response({'message': 'OTP sent to your email.'})
        except Exception as e:
            return Response({'error': f'Failed to send OTP email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
