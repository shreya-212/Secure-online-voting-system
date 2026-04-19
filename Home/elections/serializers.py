from rest_framework import serializers
from .models import Election, Candidate


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'name', 'party', 'symbol', 'photo', 'manifesto', 'election', 'created_at']
        read_only_fields = ['id', 'created_at']


class ElectionSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    total_candidates = serializers.SerializerMethodField()

    class Meta:
        model = Election
        fields = [
            'id', 'title', 'description', 'level', 'constituency',
            'state', 'district', 'village', 'start_time', 'end_time',
            'status', 'is_active', 'created_by', 'created_by_name',
            'total_candidates', 'candidates', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None

    def get_total_candidates(self, obj):
        return obj.candidates.count()


class ElectionListSerializer(serializers.ModelSerializer):
    """Compact serializer for listing elections."""
    total_candidates = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Election
        fields = [
            'id', 'title', 'level', 'constituency', 'state',
            'start_time', 'end_time', 'status', 'is_active',
            'total_candidates',
        ]

    def get_total_candidates(self, obj):
        return obj.candidates.count()
