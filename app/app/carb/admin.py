from django.contrib import admin
from django.conf import settings
from django.template.response import TemplateResponse
from django.urls import path, resolve, reverse
from django.utils.safestring import mark_safe
from django.views.generic import View

from constance import config


class AdminBaseContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(title=self._admin_title, **kwargs)
        context.update(admin.site.each_context(self.request))
        return context


class CARBAdminSite(admin.AdminSite):
    AdminBaseContextMixin = AdminBaseContextMixin
    index_title = 'Station administration'
    empty_value_display = mark_safe('<em>none</em>')
    nginx_proxy_views = (
        ('View server logs', '/logs/', 'common.view_logs'),
    )
    if settings.ZOOM_ENABLED:
        nginx_proxy_views += (('Administer Zoom over VNC', '/zoom/vnc/', 'common.view_websockify'),)

    @property
    def site_title(self):
        return f'{config.STATION_NAME} admin'
    site_header = site_title

    def __init__(self, *args, **kwargs):
        self.extra_urls = []
        super().__init__(*args, **kwargs)

    def each_context(self, request):
        context = super().each_context(request)
        current_url_name = resolve(request.path_info).url_name
        # Registered views
        extra_urls = [
            # (title, url, is_external)
            (title, reverse(f'admin:{pattern.name}'), False)
            for title, pattern, permission in self.extra_urls
            if permission is None or request.user.has_perm(permission)
        ]
        for title, url, permission in self.nginx_proxy_views:
            if request.user.has_perm(permission):
                extra_urls.append((title, url, True))

        context.update({
            'current_url_name': current_url_name,
            'extra_urls': sorted(extra_urls),
            'is_extra_url': any(current_url_name == pattern.name for _, pattern, _ in self.extra_urls),
        })
        return context

    def register_view(self, route, title, kwargs=None, name=None):
        if name is None:
            name = route.replace('/', '').replace('-', '_')

        def register(cls_or_func):
            cls_or_func._admin_title = title
            view = self.admin_view(cls_or_func.as_view() if issubclass(cls_or_func, View) else cls_or_func)
            pattern = path(route=route, view=self.admin_view(view), kwargs=kwargs, name=name)
            permission = getattr(cls_or_func, 'permission_required', None)
            self.extra_urls.append((title, pattern, permission))
            return cls_or_func
        return register

    def app_list_extra(self, request, extra_context=None):
        context = {
            **self.each_context(request),
            'title': 'Additional Settings',
            **(extra_context or {}),
        }
        request.current_app = self.name
        return TemplateResponse(request, self.index_template or 'admin/app_list_extra.html', context)

    def get_urls(self):
        return super().get_urls() + [pattern for _, pattern, _ in self.extra_urls] + [
            path('additional-settings/', self.admin_view(self.app_list_extra), name='app_list_extra')
        ]
