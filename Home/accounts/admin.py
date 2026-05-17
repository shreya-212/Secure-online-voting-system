from django.contrib import admin
from .models import User, OTP, VoterVerification, Constituency, Assembly, Village, Booth, VoterRoll, VillageAdmin, RegistrationRequest

@admin.register(Constituency)
class ConstituencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')

@admin.register(Assembly)
class AssemblyAdmin(admin.ModelAdmin):
    list_display = ('name', 'constituency')

@admin.register(Village)
class VillageModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'assembly')

@admin.register(Booth)
class BoothAdmin(admin.ModelAdmin):
    list_display = ('name', 'village')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'voter_id', 'role', 'village', 'state', 'is_verified', 'created_at')
    list_filter = ('role', 'is_verified', 'state')
    search_fields = ('username', 'voter_id', 'email', 'first_name', 'last_name')

@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'is_used', 'expires_at')

@admin.register(VoterVerification)
class VoterVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'submitted_voter_id', 'created_at')
    list_filter = ('status',)

@admin.register(VoterRoll)
class VoterRollAdmin(admin.ModelAdmin):
    list_display = ('voter_id', 'full_name', 'email', 'village', 'state', 'designated_role', 'is_registered')
    list_filter = ('state', 'designated_role', 'is_registered')
    search_fields = ('voter_id', 'full_name', 'email')

@admin.register(VillageAdmin)
class VillageAdminModelAdmin(admin.ModelAdmin):
    list_display = ('admin_id', 'full_name', 'email', 'village', 'state', 'designated_role', 'is_registered')
    list_filter = ('state', 'designated_role', 'is_registered')
    search_fields = ('admin_id', 'full_name', 'email')

@admin.register(RegistrationRequest)
class RegistrationRequestAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'voter_id', 'email', 'village', 'state', 'status', 'ai_score', 'created_at')
    list_filter = ('status', 'state')
    search_fields = ('voter_id', 'full_name', 'email')
    readonly_fields = ('ai_score', 'ai_details', 'created_at', 'updated_at', 'forwarded_at', 'resolved_at')
