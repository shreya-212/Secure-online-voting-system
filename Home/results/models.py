from django.db import models
import uuid


class ElectionResult(models.Model):
    """Stored result for each candidate in an election."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey('elections.Election', on_delete=models.CASCADE, related_name='results')
    candidate = models.ForeignKey('elections.Candidate', on_delete=models.CASCADE, related_name='results')
    total_votes = models.PositiveIntegerField(default=0)
    is_winner = models.BooleanField(default=False)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'election_results'
        unique_together = ('election', 'candidate')
        ordering = ['-total_votes']

    def __str__(self):
        winner = " ★" if self.is_winner else ""
        return f"{self.candidate.name}: {self.total_votes} votes{winner}"
