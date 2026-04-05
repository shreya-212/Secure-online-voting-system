from django.contrib import admin
from django.urls import path
from .views import RegisterView,Login_view

urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    path('login/',Login_view.as_view(),name='login')
]