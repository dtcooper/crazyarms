from django.urls import path

from . import views

urlpatterns = [
    path('dj-auth/', views.dj_auth, name='dj_auth'),
    path('log-track/', views.log_track, name='log_track'),
    path('next-track/', views.next_track, name='next_track'),
]
