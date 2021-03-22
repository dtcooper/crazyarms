import datetime
from io import StringIO
import json
import logging
import secrets
import shlex

from dotenv import dotenv_values
from huey.exceptions import TaskLockedException
import pytz

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from constance import config
from django_redis import get_redis_connection
from django_select2.views import AutoResponseView
from huey.contrib import djhuey

from autodj.models import AudioAsset
from broadcast.models import Broadcast, BroadcastAsset
from common.admin import send_set_password_email
from common.mail import send_mail
from common.models import User, filter_inactive_group_queryset
from crazyarms import constants
from gcal.models import GCalShow
from services.liquidsoap import harbor
from services.models import PlayoutLogEntry
from services.services import ZoomService

from .forms import AutoDJRequestsForm, FirstRunForm, UserProfileForm, ZoomForm, pretty_seconds
from .tasks import stop_zoom_broadcast

logger = logging.getLogger(f"crazyarms.{__name__}")


class FormErrorMessageMixin:
    error_message = "There was a problem submitting the form. Please correct any errors below."

    def form_invalid(self, form):
        messages.error(self.request, self.error_message)
        return super().form_invalid(form)


class FirstRunView(SuccessMessageMixin, FormErrorMessageMixin, FormView):
    template_name = "webui/form.html"
    form_class = FirstRunForm
    success_url = reverse_lazy("status")
    success_message = (
        "Crazy Arms Radio has successfully been setup! You can change any of "
        "the settings that you chose in the admin section."
    )
    extra_context = {
        "station_name_override": "Crazy Arms Radio Backend",
        "hide_nav": True,
        "submit_text": "Run Initial Setup",
        "title": "Initial Setup",
        "form_description": (
            "Welcome to Crazy Arms! Since no account has been created, you'll need to "
            "create a new administrator and choose from the settings below before "
            "starting."
        ),
    }

    def dispatch(self, request, *args, **kwargs):
        # Only work if no user exists
        if User.objects.exists():
            return redirect("status")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


class AutoDJRequestsAllowedMixin:
    def dispatch(self, request, *args, **kwargs):
        if not (self.request.user.is_authenticated and self.request.user.has_autodj_request_permission()):
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)


class AutoDJRequestChoicesView(AutoDJRequestsAllowedMixin, AutoResponseView):
    pass


class AutoDJRequestAJAXFormView(AutoDJRequestsAllowedMixin, FormView):
    form_class = AutoDJRequestsForm

    def get(self, request, *args, **kwargs):
        return HttpResponseNotAllowed(("POST",))

    def form_valid(self, form):
        audio_asset = form.cleaned_data["asset"]
        if audio_asset.queue_autodj_request():
            response = f"You successfully queued {audio_asset}."
        else:
            response = f"An error occurred while requesting {audio_asset}: queue full or request already exists."
        return HttpResponse(response, content_type="text/plain")


class StatusView(LoginRequiredMixin, TemplateView):
    template_name = "webui/status.html"
    extra_context = {"title": "Stream Status"}
    SHOW_NUM_UPCOMING = 5

    def dispatch(self, request, *args, **kwargs):
        if not User.objects.exists():
            return redirect("first_run")
        else:
            return super().dispatch(request, *args, **kwargs)

    def get_upcoming_status_data(self):
        upcoming_broadcasts = Broadcast.objects.filter(
            status=Broadcast.Status.QUEUED, asset__status=BroadcastAsset.Status.READY
        ).order_by("-scheduled_time")[: self.SHOW_NUM_UPCOMING]
        data = [
            (
                broadcast.scheduled_time,
                f"{broadcast.asset.title} by {broadcast.creator.get_full_name() if broadcast.creator else None}",
                "scheduled",
            )
            for broadcast in upcoming_broadcasts
        ]

        now = timezone.now()
        # current shows
        data.extend(
            [
                ("now", f"{show.title or 'Untitled Show'} ({pretty_seconds(show.end - show.start)})", "live")
                for show in GCalShow.objects.filter(start__lte=now, end__gte=now)[: self.SHOW_NUM_UPCOMING]
            ]
        )
        # future shows
        data.extend(
            [
                (show.start, f"{show.title or 'Untitled Show'} ({pretty_seconds(show.end - show.start)})", "live")
                for show in GCalShow.objects.filter(start__gte=now)[: self.SHOW_NUM_UPCOMING]
            ]
        )

        # Format for template
        return [
            {
                "date": date_format(timezone.localtime(date), "SHORT_DATETIME_FORMAT")
                if isinstance(date, datetime.datetime)
                else date,
                "title": title,
                "type": type,
            }
            for date, title, type in sorted(
                # Treat strings ("now") as highest sort
                data,
                key=lambda item: pytz.utc.localize(datetime.datetime.min) if isinstance(item[0], str) else item[0],
            )[: self.SHOW_NUM_UPCOMING]
        ]

    def get(self, request, *args, **kwargs):
        if request.GET.get("upcoming_status_ajax"):
            return JsonResponse(self.get_upcoming_status_data(), safe=False)
        else:
            return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "autodj_requests_form": AutoDJRequestsForm() if self.request.user.has_autodj_request_permission() else None,
            "liquidsoap_status": harbor.status(safe=True, as_dict=True),
            "upcoming_status": self.get_upcoming_status_data(),
        }


class InfoView(LoginRequiredMixin, TemplateView):
    template_name = "webui/info.html"

    def get_context_data(self, **kwargs):
        sftp_allowable_models = self.request.user.get_sftp_allowable_models()
        return {
            "has_sftp": bool(sftp_allowable_models),
            "has_sftp_playlists_by_folder": AudioAsset in sftp_allowable_models,
            "title": "Server Information",
            **super().get_context_data(**kwargs),
        }


class BanListView(PermissionRequiredMixin, TemplateView):
    template_name = "webui/ban_list.html"
    permission_required = "common.can_boot"
    extra_context = {"title": "DJ Ban List"}

    def get_context_data(self, **kwargs):
        bans = []
        for key in cache.keys(f"{constants.CACHE_KEY_HARBOR_BAN_PREFIX}*"):
            user_id = key.removeprefix(constants.CACHE_KEY_HARBOR_BAN_PREFIX)
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
            else:
                seconds_left = cache.ttl(key)
                banned_until = timezone.localtime() + datetime.timedelta(seconds=seconds_left)
                bans.append(
                    (
                        # Reverse sort by seconds left
                        -seconds_left,
                        user.get_full_name(),
                        user_id,
                        date_format(banned_until, "DATETIME_FORMAT"),
                    )
                )

        return {
            **super().get_context_data(**kwargs),
            "bans": [ban[1:] for ban in sorted(bans)],
        }

    def post(self, request):
        # TODO: simple formview with a model choice field for user?
        user = get_object_or_404(User, id=request.POST.get("user_id"))
        cache.delete(f"{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{user.id}")
        messages.success(request, f"The ban on {user.get_full_name()} has been lifted.")
        return redirect("banlist")


class ZoomView(LoginRequiredMixin, SuccessMessageMixin, FormErrorMessageMixin, FormView):
    template_name = "webui/zoom.html"
    form_class = ZoomForm
    success_url = reverse_lazy("zoom")
    success_message = (
        "A Zoom broadcast has been succesfully started. (If applicable, please admit the Broadcast Bot into your room.)"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.redis = get_redis_connection()
        self.room_env = self.redis.get(constants.REDIS_KEY_ROOM_INFO)
        self.room_ttl = max(self.redis.ttl(constants.REDIS_KEY_ROOM_INFO), 0)
        self.current_auth = False

        if self.room_env:
            self.room_env = dotenv_values(stream=StringIO(self.room_env.decode("utf-8")))
        else:
            self.room_env = {}

        self.zoom_user = None
        self.service = ZoomService()

    def dispatch(self, request, *args, **kwargs):
        if not settings.ZOOM_ENABLED or request.user.harbor_auth == User.HarborAuth.NEVER:
            return redirect("status")

        try:
            self.zoom_user = User.objects.get(id=self.room_env.get("MEETING_USER_ID"))
        except User.DoesNotExist:
            pass

        return super().dispatch(request, *args, **kwargs)

    @cached_property
    def zoom_is_running_cached(self):
        # Slow, so we cache it
        return self.service.is_zoom_running()

    def post(self, request):
        try:
            with djhuey.lock_task("zoom-edit-lock"):
                if request.POST.get("stop_zoom"):
                    if request.user.is_superuser or self.zoom_user == self.request.user:
                        task_id = self.room_env.get("STOP_TASK_ID")
                        if task_id:
                            djhuey.revoke_by_id(task_id)
                        stop_zoom_broadcast.call_local()
                        messages.info(request, "Zoom broadcast was stopped.")
                        return redirect("zoom")
                return super().post(request)
        except TaskLockedException:
            messages.warning(
                request,
                "Zoom action blocked. Multiple users editing configuration. Please try again.",
            )
            return redirect("zoom")

    def get_initial(self):
        show_name = self.current_auth.title
        if config.APPEND_LIVE_ON_STATION_NAME_TO_METADATA:
            # Make sure this matches up with title copy in common/models.py:User.currently_harbor_authorized() + below
            show_name = show_name.removesuffix(f" LIVE on {config.STATION_NAME}")

        return {**super().get_initial(), "show_name": show_name}

    def get_form_kwargs(self):
        now = timezone.now()
        self.current_auth = self.request.user.currently_harbor_authorized(now=now, should_log=False)

        bound = None
        if self.current_auth.end:
            bound = min(
                self.current_auth.end,
                now + datetime.timedelta(minutes=config.ZOOM_DEFAULT_SHOW_LENTH_MINUTES),
            )

        return {
            "zoom_is_running": self.zoom_is_running_cached,
            "currently_authorized": self.current_auth.authorized,
            "now": now,
            "user": self.request.user,
            "authorization_time_bound": bound,
            **super().get_form_kwargs(),
        }

    def form_valid(self, form):
        logger.info(f"User {self.request.user} starting Zoom show")
        meeting_id, meeting_pwd = form.cleaned_data["zoom_room"]

        stop_task = stop_zoom_broadcast.schedule(delay=form.cleaned_data["ttl"])
        room_env = {
            "MEETING_ID": meeting_id,
            "MEETING_USER_ID": str(self.request.user.id),
            "MEETING_USERNAME": self.request.user.username,
            "MEETING_PWD": meeting_pwd,
            "STOP_TASK_ID": stop_task.id,
        }
        # A bit jenky, but the zoom-runner.sh script evals this
        room_env_str = "".join(f"{key}={shlex.quote(value)}\n" for key, value in room_env.items())

        show_name = form.cleaned_data["show_name"]
        if config.APPEND_LIVE_ON_STATION_NAME_TO_METADATA:
            # Make sure this matches up with title copy in common/models.py:User.currently_harbor_authorized() + above
            show_name += f" LIVE on {config.STATION_NAME}"

        harbor.zoom_metadata(json.dumps(show_name))

        self.redis.set(constants.REDIS_KEY_ROOM_INFO, room_env_str, ex=form.cleaned_data["ttl"])
        self.service.supervisorctl("restart", "zoom-runner")

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "currently_authorized": self.current_auth.authorized,
            "submit_text": "Start Zoom Broadcast Now",
            "title": "Zoom Broadcasting",
            "zoom_is_running": self.zoom_is_running_cached,
            "zoom_belongs_to_current_user": self.zoom_user == self.request.user,
            "zoom_user": self.zoom_user,
            "zoom_ttl": (timezone.now() + datetime.timedelta(seconds=self.room_ttl)) if self.room_ttl else None,
        }


class UserProfileView(LoginRequiredMixin, SuccessMessageMixin, FormErrorMessageMixin, UpdateView):
    form_class = UserProfileForm
    success_message = "Your user profile was successfully updated."
    success_url = reverse_lazy("profile")
    template_name = "webui/profile.html"
    extra_context = {
        "title": "Edit Your User Profile",
        "submit_text": "Update User Profile",
    }

    def get_context_data(self, *args, **kwargs):
        groups = None
        if not self.request.user.is_superuser:
            groups = sorted(filter_inactive_group_queryset(self.request.user.groups.values_list("name", flat=True)))
        return {**super().get_context_data(*args, **kwargs), "groups": groups}

    def get_object(self, **kwargs):
        return self.request.user

    def form_valid(self, form):
        email = form.cleaned_data.get("update_email")
        if email:
            # Token doesn't need to be log, not used for signing, just in the user session
            session_token = self.request.session["update_email_token"] = secrets.token_urlsafe(12)
            token = signing.dumps(
                [self.request.user.id, session_token, email],
                salt="update:email",
                compress=True,
            )
            url = self.request.build_absolute_uri(reverse("profile_email_update", kwargs={"token": token}))

            if send_mail(
                email,
                f"Verify Email Address on {config.STATION_NAME}",
                f"Please go to the following URL to verify your email address: {url}",
                request=self.request,
            ):
                messages.warning(
                    self.request,
                    f"A verification email was sent to {email}. To complete your email "
                    "address update, please open it and follow the verification link. If you don't "
                    "receive an email, make sure you've entered the address correctly, and check your "
                    "spam folder.",
                )

        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        if settings.RTMP_ENABLED and self.request.POST.get("update_stream_key"):
            user = self.get_object()
            user.stream_key = None  # save() will regenerate if it's None
            user.save()
            messages.success(
                request,
                "Your stream key has successfully been updated. Copy the new value below.",
            )
            return redirect(self.success_url)
        else:
            return super().post(request, *args, **kwargs)


class UserProfileEmailUpdateView(LoginRequiredMixin, View):
    LINK_MAX_AGE = 60 * 60 * 12

    def get(self, request, token, *args, **kwargs):
        success = False

        try:
            user_id, session_token, email = signing.loads(token, salt="update:email", max_age=self.LINK_MAX_AGE)
        except signing.SignatureExpired:
            messages.error(
                request,
                "The link you provided to change your email has expired. Please try again.",
            )
        except signing.BadSignature:
            pass
        else:
            user = self.request.user
            current_session_token = self.request.session.pop("update_email_token", None)

            if (
                not User.objects.filter(email=email).exists()
                and user_id == self.request.user.id
                and current_session_token is not None
                and current_session_token == session_token
            ):
                user.email = email
                user.save()
                success = True
                messages.success(request, f"Your email address was updated to {email}.")

        if not success:
            messages.error(
                request,
                "The link you provided to change your password was invalid. Please try again.",
            )

        return redirect("profile")


class SetPasswordByEmailView(SuccessMessageMixin, FormErrorMessageMixin, FormView):
    form_class = SetPasswordForm
    success_url = reverse_lazy("status")
    success_message = "Your password was set and you've been logged in."
    template_name = "webui/password_set.html"

    def dispatch(self, request, token, *args, **kwargs):
        if not settings.EMAIL_ENABLED:
            return redirect("status")

        try:
            user_id, self.newly_created, self.cache_token = signing.loads(token, salt="set:password")
        except signing.BadSignature:
            return redirect("status")

        if not cache.get(f"{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{self.cache_token}:valid"):
            messages.error(request, "The link you provided is no longer valid.")
            return redirect("status")

        try:
            self.user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return redirect("status")

        if not self.user.is_active:
            messages.warning(
                request,
                "Your account is locked. Please contact the station administration.",
            )
            return redirect("login")

        self.cache_token_usable = cache.get(f"{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{self.cache_token}:usable")
        return super().dispatch(request, token=token, *args, **kwargs)

    def get_title(self):
        return f'{"New Account" if self.newly_created else "Set"} Password'

    def get(self, request, token, *args, **kwargs):
        if not self.cache_token_usable:
            messages.warning(
                self.request,
                "The link you followed is invalid. Please click the button below to resend "
                "an email to the address on file.",
            )
        return super().get(request, token, *args, **kwargs)

    def post(self, request, token, *args, **kwargs):
        if self.cache_token_usable:
            return super().post(request, *args, **kwargs)
        elif request.POST.get("send_new_email"):
            send_set_password_email(request, self.user, newly_created=self.newly_created)
            return render(
                request,
                "webui/base.html",
                {
                    "title": self.get_title(),
                    "simple_content": "An email has been sent to the address on file.",
                },
            )
        else:
            return redirect("password_set_by_email", token=token)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(),
            "newly_created": self.newly_created,
            "title": self.get_title(),
            "cache_token_usable": self.cache_token_usable,
        }

    def get_form_kwargs(self):
        return {"user": self.user, **super().get_form_kwargs()}

    def form_valid(self, form):
        form.save()
        cache.delete(f"{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{self.cache_token}:usable")
        cache.delete(f"{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{self.cache_token}:valid")
        login(self.request, self.user)
        return super().form_valid(form)


class GCalView(LoginRequiredMixin, TemplateView):
    template_name = "webui/gcal.html"
    extra_context = {"title": "My Scheduled Shows"}

    def dispatch(self, *args, **kwargs):
        if not config.GOOGLE_CALENDAR_ENABLED:
            return redirect("status")
        return super().dispatch(*args, **kwargs)


class BootView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        # Get pretty copy from front-end because why not?
        user_id, time, ban_text = (
            request.POST.get("user_id"),
            request.POST.get("time"),
            request.POST.get("text"),
        )
        response = "You don't have permission to do that."

        if user_id is None or time is None:
            response = "Malformed request."

        # Has permission to do operation
        elif (time == "permanent" and request.user.is_superuser) or request.user.has_perm("common.can_boot"):
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                response = "User does not exist."

            else:
                # Only superuser can perma-ban
                if time == "permanent" and request.user.is_superuser:
                    user.harbor_auth = User.HarborAuth.NEVER
                    user.save()
                    harbor.dj_harbor__stop()
                    logger.info(f"{self.request.user} banned {user} permanently (set harbor_auth = never)")
                    response = (
                        f"{user.get_full_name()} banned permanently. To undo this change, go the Station"
                        " Admin and change their harbor authorization."
                    )
                else:
                    try:
                        # XXX Covers case where user asks for "perm" (permanent), since ValueError is thrown
                        time = int(time)
                    except ValueError:
                        pass
                    else:
                        if time > 0:
                            cache.set(
                                f"{constants.CACHE_KEY_HARBOR_BAN_PREFIX}{user.id}",
                                True,
                                timeout=time,
                            )
                            harbor.dj_harbor__stop()
                            logger.info(f"{self.request.user} banned {user} for {ban_text}")
                            response = (
                                f"{user.get_full_name()} banned for {ban_text}. To undo, visit the DJ Ban List page."
                            )

        return HttpResponse(response, content_type="text/plain")


class SkipView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        status = harbor.status(safe=True, as_dict=True)
        if status is None:
            response = "Invalid response from harbor"
        else:
            response = "You don't have permission to do that."
            skippable_sources = status["skippable_sources"]
            if request.user.has_perm("broadcast.change_broadcast"):
                source_id = request.POST.get("id")
                if source_id is None:
                    response = "Malformed request."
                elif source_id not in skippable_sources:
                    response = f"{source_id} not a skippable source."
                else:
                    source_name = request.POST.get("name", "Unknown")
                    getattr(harbor, f"{source_id}.skip")()
                    PlayoutLogEntry.objects.create(
                        event_type=PlayoutLogEntry.EventType.TRACK,
                        user=request.user,
                        description=f"{request.user.get_full_name()} manually skipped track",
                        active_source=source_name,
                    )
                    response = f"You successfully skipped the current track on {source_name}."
                    logger.info(f"{self.request.user} skipped track on {source_id}")
        return HttpResponse(response, content_type="text/plain")


class PlayoutLogView(LoginRequiredMixin, ListView):
    MAX_ENTRIES = 250
    template_name = "webui/playout_log.html"
    queryset = PlayoutLogEntry.objects.order_by("-created")[:MAX_ENTRIES]
    extra_context = {"title": "Playout Log", "MAX_ENTRIES": MAX_ENTRIES}


class PasswordChangeView(SuccessMessageMixin, FormErrorMessageMixin, auth_views.PasswordChangeView):
    success_url = reverse_lazy("profile")
    template_name = "webui/form.html"
    title = "Change Your Password"
    if settings.RTMP_ENABLED:
        success_message = (
            "Your password was successfully changed and a new RTMP stream key was generated. "
            "Copy the new stream key below."
        )
    else:
        success_message = "Your password was successfully changed."

    def __init__(self):
        context = {"submit_text": "Change Password"}
        if settings.RTMP_ENABLED:
            context["form_description"] = (
                "If you update your password, a new RTMP stream key will be generated. "
                "You'll need to copy it from your profile page after updating."
            )
        super().__init__(extra_context=context)


class PasswordResetView(SuccessMessageMixin, auth_views.PasswordResetView):
    # TODO: warn about locked account and email + not sent
    # Maybe we roll our own here, then we could use common/mail.py:send_mail()
    success_message = (
        "A password reset email has been sent to %(email)s. If an account exists with that email "
        "address, you should should receive it shortly. If you don't receive an email, make sure you've"
        "entered your address correctly, and check your spam folder."
    )
    success_url = reverse_lazy("login")
    template_name = "webui/form.html"
    title = "Reset Your Password"
    extra_context = {
        "submit_text": "Send Password Reset Email",
        "form_description": "Enter your email address below, and we’ll email instructions you for setting a new one.",
    }

    @property
    def extra_email_context(self):
        return {"site_name": config.STATION_NAME}


class PasswordResetConfirmView(SuccessMessageMixin, FormErrorMessageMixin, auth_views.PasswordResetConfirmView):
    post_reset_login = True
    success_url = reverse_lazy("status")
    success_message = "Your password has been successfully reset and you have been logged in."
    template_name = "webui/form.html"
    title = "Enter Your New Password"
    extra_context = {
        "submit_text": "Reset Password",
        "form_description": "Please select a new password. Enter it twice for confirmation.",
    }


@csrf_exempt
def nginx_protected(request, module):
    if module == "sse":
        has_perm = request.user.is_authenticated
    else:
        has_perm = request.user.has_perm(f"common.view_{module}")

    if has_perm:
        logger.info(f"allowing {request.user} access to module: {module}")
        response = HttpResponse()
        response["X-Accel-Redirect"] = f"/protected{request.get_full_path()}"
    else:
        response = HttpResponseForbidden()
    return response
