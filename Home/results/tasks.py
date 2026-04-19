"""Celery tasks for result calculation. Works without Celery installed."""
import functools

try:
    from celery import shared_task
except ImportError:
    # Fallback: run synchronously if Celery not installed
    def shared_task(func=None, *args, **kwargs):
        if func is None:
            return lambda f: f
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return func(*a, **kw)
        wrapper.delay = wrapper
        wrapper.apply_async = lambda *a, **kw: wrapper(*a, **kw)
        return wrapper

from django.db.models import Count
from django.utils import timezone


@shared_task
def calculate_election_results(election_id):
    from elections.models import Election, Candidate
    from voting.models import Vote
    from .models import ElectionResult

    try:
        election = Election.objects.get(id=election_id)
    except Election.DoesNotExist:
        return f"Election {election_id} not found"

    vote_counts = (
        Vote.objects.filter(election=election)
        .values('candidate')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    ElectionResult.objects.filter(election=election).delete()

    max_votes = 0
    for vc in vote_counts:
        if vc['total'] > max_votes:
            max_votes = vc['total']
        ElectionResult.objects.create(
            election=election,
            candidate_id=vc['candidate'],
            total_votes=vc['total'],
        )

    candidates_with_votes = [vc['candidate'] for vc in vote_counts]
    for candidate in Candidate.objects.filter(election=election).exclude(id__in=candidates_with_votes):
        ElectionResult.objects.create(election=election, candidate=candidate, total_votes=0)

    if max_votes > 0:
        ElectionResult.objects.filter(election=election, total_votes=max_votes).update(is_winner=True)

    election.status = 'completed'
    election.save()
    return f"Results calculated for {election.title}"


@shared_task
def auto_calculate_all_ended_elections():
    from elections.models import Election

    ended = Election.objects.filter(end_time__lt=timezone.now(), status='active')
    for election in ended:
        calculate_election_results(str(election.id))
    return f"Triggered result calculation for {ended.count()} elections"
