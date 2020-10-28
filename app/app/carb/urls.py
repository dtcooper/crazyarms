from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from constance import config


class PasswordResetView(auth_views.PasswordResetView):
    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'site_header': admin.site.site_header}

    @property
    def extra_email_context(self):
        return {'domain': settings.DOMAIN_NAME, 'site_name': config.STATION_NAME}


urlpatterns = [
    path('', include('webui.urls')),
    path('api/', include('api.urls')),
    path('admin/', admin.site.urls),
]

if settings.EMAIL_ENABLED:
    urlpatterns += [
        path('admin/password-reset/', PasswordResetView.as_view(), name='admin_password_reset'),
        path('admin/password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done',),
        path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
        path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    ]
