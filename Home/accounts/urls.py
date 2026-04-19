from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('otp-verify/', views.OTPVerifyView.as_view(), name='otp_verify'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('dashboard-stats/', views.DashboardStatsView.as_view(), name='dashboard_stats'),
    path('extract-card/', views.ExtractCardView.as_view(), name='extract_card'),
    path('verify-identity/', views.VoterVerifyIdentityView.as_view(), name='verify_identity'),
    path('register-face/', views.RegisterFaceView.as_view(), name='register_face'),
    path('verify-face/', views.VerifyFaceView.as_view(), name='verify_face'),
]
