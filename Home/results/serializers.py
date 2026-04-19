from rest_framework import serializers
from .models import ElectionResult


class ElectionResultSerializer(serializers.ModelSerializer):
    candidate_name = serializers.CharField(source='candidate.name', read_only=True)
    candidate_party = serializers.CharField(source='candidate.party', read_only=True)
    candidate_symbol = serializers.CharField(source='candidate.symbol', read_only=True)
    election_title = serializers.CharField(source='election.title', read_only=True)

    class Meta:
        model = ElectionResult
        fields = [
            'id', 'election', 'election_title', 'candidate',
            'candidate_name', 'candidate_party', 'candidate_symbol',
            'total_votes', 'is_winner', 'calculated_at',
        ]
