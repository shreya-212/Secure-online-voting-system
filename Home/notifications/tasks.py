"""Celery tasks for notifications. Works without Celery installed."""
import functools

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, *args, **kwargs):
        if func is None:
            return lambda f: f
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return func(*a, **kw)
        wrapper.delay = wrapper
        wrapper.apply_async = lambda *a, **kw: wrapper(*a, **kw)
        return wrapper


@shared_task
def send_vote_confirmation(user_id, election_id):
    from accounts.models import User
    from elections.models import Election
    from .models import Notification

    try:
        user = User.objects.get(id=user_id)
        election = Election.objects.get(id=election_id)
        Notification.objects.create(
            user=user,
            title='Vote Confirmed ✓',
            message=f'Your vote in "{election.title}" has been recorded securely.',
            type='vote_confirm',
        )
        print(f"[MOCK SMS] Vote confirmation sent to {user.phone or user.email}")
        return f"Vote confirmation sent to {user.email}"
    except Exception as e:
        return f"Error: {str(e)}"


@shared_task
def send_election_reminder(election_id):
    from accounts.models import User
    from elections.models import Election
    from .models import Notification

    try:
        election = Election.objects.get(id=election_id)
        if election.level == 'national':
            voters = User.objects.filter(role='voter', is_verified=True)
        elif election.level == 'state':
            voters = User.objects.filter(role='voter', is_verified=True, state=election.state)
        else:
            voters = User.objects.filter(
                role='voter', is_verified=True,
                state=election.state, district=election.district, village=election.village
            )

        notifications = [
            Notification(
                user=voter,
                title=f'Election Reminder: {election.title}',
                message=f'Voting ends on {election.end_time.strftime("%d %b %Y, %I:%M %p")}.',
                type='election_reminder',
            )
            for voter in voters
        ]
        Notification.objects.bulk_create(notifications)
        return f"Reminders sent to {len(notifications)} voters"
    except Exception as e:
        return f"Error: {str(e)}"


@shared_task
def send_results_notification(election_id):
    from accounts.models import User
    from elections.models import Election
    from results.models import ElectionResult
    from .models import Notification

    try:
        election = Election.objects.get(id=election_id)
        winner = ElectionResult.objects.filter(election=election, is_winner=True).first()
        if not winner:
            return "No results available"

        winner_info = f"{winner.candidate.name} ({winner.candidate.party})"
        if election.level == 'national':
            voters = User.objects.filter(role='voter', is_verified=True)
        elif election.level == 'state':
            voters = User.objects.filter(role='voter', is_verified=True, state=election.state)
        else:
            voters = User.objects.filter(
                role='voter', is_verified=True,
                state=election.state, district=election.district, village=election.village
            )

        notifications = [
            Notification(
                user=voter,
                title=f'Results: {election.title}',
                message=f'Winner: {winner_info}.',
                type='results',
            )
            for voter in voters
        ]
        Notification.objects.bulk_create(notifications)
        return f"Results notifications sent to {len(notifications)} voters"
    except Exception as e:
        return f"Error: {str(e)}"
