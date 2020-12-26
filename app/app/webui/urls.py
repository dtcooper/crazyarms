from django.contrib.auth import views as auth_views
from django.conf import settings
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
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('info/', views.InfoView.as_view(), name='info'),
    path('password-set/<token>/', views.SetPasswordView.as_view(), name='password_set'),
    path('playout-log/', views.PlayoutLogView.as_view(), name='playout_log'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/email/<token>/', views.UserProfileEmailUpdateView.as_view(), name='profile_email_update'),
    path('scheduled-shows/', views.GCalView.as_view(), name='gcal'),
    path('status/autodj-request/', views.AutoDJRequestAJAXFormView.as_view(), name='autodj_request'),
    path('status/autodj-request/choices/', views.AutoDJRequestChoicesView.as_view(), name='autodj_request_choices'),
    path('status/boot/', views.BootView.as_view(), name='boot'),
    path('status/skip/', views.SkipView.as_view(), name='skip'),
    path('zoom/', views.ZoomView.as_view(), name='zoom'),
    re_path('^(?P<module>logs|websockify|telnet|sse)', views.nginx_protected, name='nginx_protected'),
]

if settings.EMAIL_ENABLED:
    urlpatterns += [
        path('password-reset/', views.PasswordResetView.as_view(), name='admin_password_reset'),
        path('password-reset/<uidb64>/<token>/',
             views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    ]
