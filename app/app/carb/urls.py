from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.urls import include, path, reverse_lazy

from constance import config


class PasswordResetView(SuccessMessageMixin, auth_views.PasswordResetView):
    success_message = ('A password reset email has been sent to %(email)s. If an account exists with that email '
                       "address, you should should receive it shortly. If you don’t receive an email, make sure you've"
                       'entered your address correctly, and check your spam folder.')
    success_url = reverse_lazy('login')
    template_name = 'webui/form.html'
    title = 'Reset Your Password'

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs), 'site_header': admin.site.site_header,
            'submit_text': 'Send Password Reset Email',
            'form_description': "Enter your email address below, and we’ll email instructions for setting a new one.",
        }

    @property
    def extra_email_context(self):
        return {'domain': settings.DOMAIN_NAME, 'site_name': config.STATION_NAME}


class PasswordResetConfirmView(SuccessMessageMixin, auth_views.PasswordResetConfirmView):
    post_reset_login = True
    success_url = reverse_lazy('status')
    success_message = 'Your password has been successfully reset and you have been logged in.'
    template_name = 'webui/form.html'
    title = 'Enter Your New Password'

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), 'submit_text': 'Reset Password',
                'form_description': 'Please select a new password. Enter it twice for confirmation.'}


urlpatterns = [
    path('', include('webui.urls')),
    path('api/', include('api.urls')),
    path('admin/', admin.site.urls),
]

if settings.EMAIL_ENABLED:
    urlpatterns += [
        path('password-reset/', PasswordResetView.as_view(), name='admin_password_reset'),
        path('password-reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    ]
