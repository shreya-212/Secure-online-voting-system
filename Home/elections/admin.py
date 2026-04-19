from django.contrib import admin
from .models import Election, Candidate


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'level', 'state', 'status', 'start_time', 'end_time']
    list_filter = ['level', 'status', 'state']
    search_fields = ['title', 'constituency']


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['name', 'party', 'symbol', 'election']
    list_filter = ['party']
    search_fields = ['name', 'party']
