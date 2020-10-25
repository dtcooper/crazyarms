from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, re_path
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView

from constance import config

from carb import views


admin.site.site_title = admin.site.site_header = lambda: f'{config.STATION_NAME} admin'
admin.site.index_title = 'Station administration'
admin.site.empty_value_display = mark_safe('<em>none</em>')

urlpatterns = [
    path('', views.StatusView.as_view(), name='status'),
    path('first-run/', views.FirstRunView.as_view(), name='first_run'),
    path('harbor/auth/', views.harbor_auth, name='harbor-auth'),
    path('calendar/', TemplateView.as_view(
        template_name='calendar.html', extra_context={'title': 'Custom Title'}), name='calendar'),
    re_path('^(?P<module>logs|websockify)', views.nginx_protected, name='nginx_protected'),
    # Auth related
    path('login/', auth_views.LoginView.as_view(extra_context={'hide_nav': True}, redirect_authenticated_user=True,
                                                template_name='auth_form.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.PasswordChangeView.as_view(), name='password_change'),
    # admin
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
