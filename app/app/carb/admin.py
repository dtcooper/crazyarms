from collections import defaultdict

from django.contrib import admin
from django.conf import settings
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
    nginx_proxy_views = (('View server logs', 'constance', '/logs/', 'common.view_logs'),)
    if settings.ZOOM_ENABLED:
        nginx_proxy_views += (('Administer Zoom over VNC', 'constance', '/zoom/vnc/', 'common.view_websockify'),)

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
        extra_urls = defaultdict(list)

        # Registered views
        for title, app_label, pattern, permission in self.extra_urls:
            if permission is None or request.user.has_perm(permission):
                extra_urls[app_label].append((title, reverse(f'admin:{pattern.name}'), False))
        for title, app_label, url, permission in self.nginx_proxy_views:
            if request.user.has_perm(permission):
                extra_urls[app_label].append((title, url, True))

        extra_url_app_label = None
        for _, app_label, pattern, _ in self.extra_urls:
            if current_url_name == pattern.name:
                extra_url_app_label = app_label
        print(extra_url_app_label)

        context.update({
            'current_url_name': current_url_name,
            'extra_urls': sorted(extra_urls.items()),
            'extra_url_app_label': extra_url_app_label,
        })
        return context

    def register_view(self, route, app_label, title, kwargs=None, name=None):
        if name is None:
            name = route.replace('/', '').replace('-', '_')

        def register(cls_or_func):
            cls_or_func._admin_title = title
            view = self.admin_view(cls_or_func.as_view() if issubclass(cls_or_func, View) else cls_or_func)
            pattern = path(route=f'{app_label}/{route}', view=self.admin_view(view), kwargs=kwargs, name=name)
            permission = getattr(cls_or_func, 'permission_required', None)
            self.extra_urls.append((title, app_label, pattern, permission))
            return cls_or_func
        return register

    def get_urls(self):
        return super().get_urls() + [pattern for _, _, pattern, _ in self.extra_urls]
