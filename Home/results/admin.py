from django.contrib import admin
from .models import ElectionResult


@admin.register(ElectionResult)
class ElectionResultAdmin(admin.ModelAdmin):
    list_display = ['election', 'candidate', 'total_votes', 'is_winner', 'calculated_at']
    list_filter = ['election', 'is_winner']
