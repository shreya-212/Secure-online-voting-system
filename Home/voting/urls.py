from django.urls import path
from . import views

urlpatterns = [
    path('cast/', views.CastVoteView.as_view(), name='cast_vote'),
    path('status/<uuid:election_id>/', views.VoteStatusView.as_view(), name='vote_status'),
]
