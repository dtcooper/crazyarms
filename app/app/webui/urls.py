from django.contrib.auth import views as auth_views
from django.urls import path, re_path

from . import views

urlpatterns = [
    path('', views.StatusView.as_view(), name='status'),
    path('first-run', views.FirstRunView.as_view(), name='first-run'),
    path('login/', auth_views.LoginView.as_view(extra_context={'hide_nav': True}, redirect_authenticated_user=True,
                                                template_name='webui/form.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.PasswordChangeView.as_view(), name='password_change'),
    re_path('^(?P<module>logs|websockify)', views.nginx_protected, name='nginx_protected'),
]
