from django.contrib import admin
from .models import User, OTP


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'voter_id', 'role', 'state', 'is_verified']
    list_filter = ['role', 'is_verified', 'state']
    search_fields = ['email', 'first_name', 'last_name', 'voter_id']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'is_used', 'created_at', 'expires_at']
    list_filter = ['is_used']
