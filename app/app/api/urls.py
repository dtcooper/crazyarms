from django.urls import path

from . import views

urlpatterns = [
    path('dj-auth/', views.DJAuthAPIView.as_view(), name='dj_auth'),
    path('next-track/', views.NextTrackAPIView.as_view(), name='next_track'),
    path('sftp-auth/', views.SFTPAuthView.as_view(), name='sftp_auth'),
    path('sftp-upload/', views.SFTPUploadView.as_view(), name='fstp_upload'),
]
