from django.conf import settings
from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path, resolve, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.generic import View

from constance import config


class AdminBaseContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(title=self._admin_title, **kwargs)
        context.update(admin.site.each_context(self.request))
        return context


class CrazyArmsAdminSite(admin.AdminSite):
    AdminBaseContextMixin = AdminBaseContextMixin
    index_title = ""
    empty_value_display = mark_safe("<em>none</em>")
    site_url = None
    nginx_proxy_views = (("View server logs", "/logs/", "common.view_logs"),)
    if settings.ZOOM_ENABLED:
        nginx_proxy_views += (("Administer Zoom over VNC", "/zoom/vnc/", "common.view_websockify"),)
    if settings.HARBOR_TELNET_WEB_ENABLED:
        nginx_proxy_views += (
            (
                "Liquidsoap harbor telnet (experimental)",
                "/telnet/",
                "common.view_telnet",
            ),
        )

    @property
    def site_title(self):
        return format_html("{} &mdash; Station Admin", config.STATION_NAME)

    site_header = site_title

    def __init__(self, *args, **kwargs):
        self.extra_urls = []
        super().__init__(*args, **kwargs)

    def app_index_extra(self, request):
        return TemplateResponse(
            request,
            self.index_template or "admin/app_index_extra.html",
            {
                **self.each_context(request),
                "title": "Miscellaneous Configuration administration",
                "app_list": False,
            },
        )

    def app_index(self, request, app_label, extra_context=None):
        return super().app_index(
            request,
            app_label,
            extra_context={**(extra_context or {}), "extra_urls": []},
        )

    def each_context(self, request):
        context = super().each_context(request)
        current_url_name = resolve(request.path_info).url_name
        is_extra_url = False
        extra_urls = []

        # Registered views
        for title, pattern, permission in self.extra_urls:
            if permission is None or request.user.has_perm(permission):
                extra_urls.append((title, reverse(f"admin:{pattern.name}"), False))
            if current_url_name == pattern.name:
                is_extra_url = True
        for title, url, permission in self.nginx_proxy_views:
            if request.user.has_perm(permission):
                extra_urls.append((title, url, True))

        context.update(
            {
                "current_url_name": current_url_name,
                "extra_urls": sorted(extra_urls),
                "is_extra_url": is_extra_url,
            }
        )
        return context

    def register_view(self, route, title, kwargs=None, name=None):
        if name is None:
            name = route.replace("/", "").replace("-", "_")

        def register(cls_or_func):
            cls_or_func._admin_title = title
            view = self.admin_view(cls_or_func.as_view() if issubclass(cls_or_func, View) else cls_or_func)
            pattern = path(
                route=f"settings/{route}",
                view=self.admin_view(view),
                kwargs=kwargs,
                name=name,
            )
            permission = getattr(cls_or_func, "permission_required", None)
            self.extra_urls.append((title, pattern, permission))
            return cls_or_func

        return register

    def get_urls(self):
        return (
            [
                path(
                    "settings/",
                    view=self.admin_view(self.app_index_extra),
                    name="app_index_extra",
                )
            ]
            + [pattern for _, pattern, _ in self.extra_urls]
            + super().get_urls()
        )
