from django.urls import path

from . import views

urlpatterns = [
    path('auth/', views.auth, name='api-auth'),
    path('next-track/', views.next_track, name='next-track'),
]
