from django.contrib.auth import views as auth_views
from django.urls import path, re_path

from . import views

urlpatterns = [
    re_path('^(?:|status/)$', views.StatusView.as_view(), name='status'),
    path('banlist/', views.BanListView.as_view(), name='banlist'),
    path('change-password/', views.PasswordChangeView.as_view(), name='password_change'),
    path('first-run/', views.FirstRunView.as_view(), name='first_run'),
    path('login/', auth_views.LoginView.as_view(
        extra_context={'hide_login_link': True, 'title': 'Login', 'submit_text': 'Login'},
        redirect_authenticated_user=True, template_name='webui/login.html'), name='login'),
    path('playout-log/', views.PlayoutLogView.as_view(), name='playout_log'),
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('scheduled-shows/', views.GCalView.as_view(), name='gcal'),
    path('status/boot/', views.status_boot, name='status_boot'),
    path('status/skip/', views.status_skip, name='status_skip'),
    path('zoom/', views.ZoomView.as_view(), name='zoom'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    re_path('^(?P<module>logs|websockify|telnet|sse)', views.nginx_protected, name='nginx_protected'),
]
