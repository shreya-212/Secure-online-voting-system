from django.contrib import admin
from .models import VoteRecord, Vote


@admin.register(VoteRecord)
class VoteRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'election', 'voted_at']
    list_filter = ['election']
    search_fields = ['user__email']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['election', 'candidate', 'vote_hash', 'timestamp']
    list_filter = ['election']
    readonly_fields = ['vote_hash']
