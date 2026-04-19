from django.db import models
from django.conf import settings
import uuid


class VoteRecord(models.Model):
    """
    Tracks WHO voted in WHICH election. Separate from the Vote itself
    to maintain anonymity — this table has no reference to which candidate
    was chosen.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vote_records')
    election = models.ForeignKey('elections.Election', on_delete=models.CASCADE, related_name='vote_records')
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vote_records'
        unique_together = ('user', 'election')  # One vote per election
        indexes = [
            models.Index(fields=['user', 'election']),
        ]

    def __str__(self):
        return f"{self.user.email} voted in {self.election.title}"


class Vote(models.Model):
    """
    Anonymous vote storage. No user FK — only links to election
    and candidate with a SHA-256 integrity hash.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey('elections.Election', on_delete=models.CASCADE, related_name='votes')
    candidate = models.ForeignKey('elections.Candidate', on_delete=models.CASCADE, related_name='votes')
    vote_hash = models.CharField(max_length=64, unique=True)  # SHA-256
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'votes'
        indexes = [
            models.Index(fields=['election', 'candidate']),
            models.Index(fields=['vote_hash']),
        ]

    def __str__(self):
        return f"Vote for {self.candidate.name} in {self.election.title}"
