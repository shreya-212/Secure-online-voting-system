from rest_framework import serializers


class CastVoteSerializer(serializers.Serializer):
    election_id = serializers.UUIDField()
    candidate_id = serializers.UUIDField()
    otp_code = serializers.CharField(max_length=6)
