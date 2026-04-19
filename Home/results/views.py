from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone

from .models import ElectionResult
from .serializers import ElectionResultSerializer
from .tasks import calculate_election_results
from elections.models import Election
from voting.models import Vote


class ElectionResultsView(APIView):
    """Get results for a specific election."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, election_id):
        try:
            election = Election.objects.get(id=election_id)
        except Election.DoesNotExist:
            return Response({'error': 'Election not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only show results after election has ended
        if election.end_time > timezone.now():
            return Response(
                {'error': 'Results are not available until the election ends.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if results exist, if not calculate them
        results = ElectionResult.objects.filter(election=election)
        if not results.exists():
            # Calculate synchronously for immediate response
            from django.db.models import Count
            from elections.models import Candidate

            vote_counts = (
                Vote.objects.filter(election=election)
                .values('candidate')
                .annotate(total=Count('id'))
                .order_by('-total')
            )

            max_votes = 0
            for vc in vote_counts:
                if vc['total'] > max_votes:
                    max_votes = vc['total']
                ElectionResult.objects.create(
                    election=election,
                    candidate_id=vc['candidate'],
                    total_votes=vc['total'],
                )

            # Candidates with 0 votes
            candidates_with_votes = [vc['candidate'] for vc in vote_counts]
            for candidate in Candidate.objects.filter(election=election).exclude(id__in=candidates_with_votes):
                ElectionResult.objects.create(election=election, candidate=candidate, total_votes=0)

            if max_votes > 0:
                ElectionResult.objects.filter(election=election, total_votes=max_votes).update(is_winner=True)

            election.status = 'completed'
            election.save()
            results = ElectionResult.objects.filter(election=election)

        total_votes = sum(r.total_votes for r in results)
        serializer = ElectionResultSerializer(results, many=True)

        return Response({
            'election': {
                'id': str(election.id),
                'title': election.title,
                'level': election.level,
                'status': election.status,
                'start_time': election.start_time,
                'end_time': election.end_time,
            },
            'total_votes': total_votes,
            'results': serializer.data,
        })


class TriggerResultCalculationView(APIView):
    """Admin-only: manually trigger result calculation."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, election_id):
        try:
            election = Election.objects.get(id=election_id)
        except Election.DoesNotExist:
            return Response({'error': 'Election not found.'}, status=status.HTTP_404_NOT_FOUND)

        calculate_election_results.delay(str(election_id))
        return Response({'message': f'Result calculation triggered for {election.title}.'})
