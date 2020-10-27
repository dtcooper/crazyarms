from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


# admin.site.site_title = admin.site.site_header = lambda: f'{config.STATION_NAME} admin'
# admin.site.index_title = 'Station administration'
# admin.site.empty_value_display = mark_safe('<em>none</em>')


urlpatterns = [
    path('', include('webui.urls')),
    path('api/', include('api.urls')),
    path('admin/', admin.site.urls),
]

if settings.EMAIL_ENABLED:
    urlpatterns += [
        path('admin/password-reset/', auth_views.PasswordResetView.as_view(), name='admin_password_reset'),
        path('admin/password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done',),
        path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
        path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    ]
