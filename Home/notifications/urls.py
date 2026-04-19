from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('<uuid:pk>/read/', views.MarkNotificationReadView.as_view(), name='mark_read'),
    path('read-all/', views.MarkAllReadView.as_view(), name='mark_all_read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread_count'),
]
