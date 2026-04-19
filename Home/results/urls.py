from django.urls import path
from . import views

urlpatterns = [
    path('<uuid:election_id>/', views.ElectionResultsView.as_view(), name='election_results'),
    path('<uuid:election_id>/calculate/', views.TriggerResultCalculationView.as_view(), name='trigger_results'),
]
