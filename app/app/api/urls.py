from django.urls import path

from . import views

urlpatterns = [
    path('dj-auth/', views.DJAuthAPIView.as_view(), name='dj_auth'),
    path('next-track/', views.NextTrackAPIView.as_view(), name='next_track'),
]
