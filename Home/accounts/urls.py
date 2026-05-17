from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('check-voter-roll/', views.CheckVoterRollView.as_view(), name='check_voter_roll'),
    path('send-voter-otp/', views.SendVoterOTPView.as_view(), name='send_voter_otp'),
    path('verify-voter-otp/', views.VerifyVoterOTPView.as_view(), name='verify_voter_otp'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('otp-verify/', views.OTPVerifyView.as_view(), name='otp_verify'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard_stats'),
    path('voter-roll/', views.VoterRollAPIView.as_view(), name='voter_roll'),
    path('voter-roll/<int:pk>/', views.VoterRollDetailAPIView.as_view(), name='voter_roll_detail'),
    path('village-admins/', views.VillageAdminAPIView.as_view(), name='village_admin_list'),
    path('village-admins/<int:pk>/', views.VillageAdminDetailAPIView.as_view(), name='village_admin_detail'),
    path('extract-card/', views.ExtractCardView.as_view(), name='extract_card'),
    path('verify-identity/', views.VoterVerifyIdentityView.as_view(), name='verify_identity'),
    path('register-face/', views.RegisterFaceView.as_view(), name='register_face'),
    path('verify-face/', views.VerifyFaceView.as_view(), name='verify_face'),
    path('password-reset-request/', views.RequestPasswordResetView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', views.ResetPasswordView.as_view(), name='password_reset_confirm'),

    # ── Chatbot Registration Request (Two-Stage Approval) ──
    path('registration-requests/', views.RegistrationRequestListView.as_view(), name='registration_request_list'),
    path('registration-requests/submit/', views.SubmitRegistrationRequestView.as_view(), name='registration_request_submit'),
    path('registration-requests/<int:pk>/forward/', views.ForwardToVoterAdminView.as_view(), name='registration_request_forward'),
    path('registration-requests/<int:pk>/approve/', views.ApproveRegistrationView.as_view(), name='registration_request_approve'),
    path('registration-requests/<int:pk>/reject/', views.RejectRegistrationView.as_view(), name='registration_request_reject'),
]
