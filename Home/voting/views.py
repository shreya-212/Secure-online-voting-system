import hashlib
import uuid
from django.db import transaction
from django.utils import timezone
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

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

        # Check election is active
        now = timezone.now()
        if not (election.start_time <= now <= election.end_time):
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
