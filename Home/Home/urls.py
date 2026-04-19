"""URL configuration for Home project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    # JWT token refresh
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # App APIs
    path('api/auth/', include('accounts.urls')),
    path('api/elections/', include('elections.urls')),
    path('api/voting/', include('voting.urls')),
    path('api/results/', include('results.urls')),
    path('api/notifications/', include('notifications.urls')),

    # Frontend pages
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('elections/', TemplateView.as_view(template_name='elections.html'), name='elections'),
    path('vote/', TemplateView.as_view(template_name='vote.html'), name='vote'),
    path('results/', TemplateView.as_view(template_name='results.html'), name='results_page'),
    path('admin-panel/', TemplateView.as_view(template_name='admin.html'), name='admin_panel'),
    path('verify/', TemplateView.as_view(template_name='verify.html'), name='verify'),
    path('register-face/', TemplateView.as_view(template_name='register_face.html'), name='register_face'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
