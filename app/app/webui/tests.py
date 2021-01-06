import os
import re
import shutil
from unittest.mock import Mock, patch
import uuid

import requests_mock

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import TransactionTestCase
from django.urls import reverse

from constance import config

from autodj.models import AudioAsset, Playlist, Rotator, Stopset, StopsetRotator
from common.models import User
from services.models import UpstreamServer

from .forms import CCMIXTER_API_URL, FirstRunForm
from .views import FirstRunView


class FirstRunTests(TransactionTestCase):
    def login_admin(self):
        admin = User.objects.create_superuser("admin", "admin@example.com", "password")
        self.client.login(username=admin.username, password="password")

    def test_renders(self):
        response = self.client.get(reverse("first_run"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "webui/form.html")
        form = response.context["form"]
        self.assertIsInstance(form, FirstRunForm)

    def assertHasMessage(self, response, message):
        messages = list(map(str, get_messages(response.wsgi_request)))
        self.assertIn(message, messages, f"Message {message} not found in request in {messages}")

    @requests_mock.Mocker()
    @patch("services.services.ServiceBase.supervisorctl")
    @patch("webui.forms.generate_random_string", lambda *args, **kwargs: "random-pw")
    @patch(
        "common.tasks.asset_download_external_url",
        lambda *args, **kwargs: Mock(id=uuid.uuid4()),
    )
    def test_post(self, requests_mock, supervisor_mock):
        ccmixter_response = open(f"{settings.BASE_DIR}/crazyarms/test_data/ccmixter.json", "rb")
        requests_mock.register_uri("GET", CCMIXTER_API_URL, body=ccmixter_response)
        requests_mock.register_uri(
            "GET",
            re.compile(r"^http://ccmixter\.org/content/"),
            text="invalid-mp3-data",
        )
        shutil.rmtree("/config", ignore_errors=True)

        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UpstreamServer.objects.count(), 0)

        response = self.client.post(
            reverse("first_run"),
            {
                "username": "admin",
                "email": "admin@crazyarms.example",
                "password1": "user-pw",
                "password2": "user-pw",
                "icecast_admin_password": "icecast-pw",
                "generate_sample_assets": "True",
                "station_name": "Test Station",
            },
        )
        self.assertRedirects(response, reverse("status"), fetch_redirect_response=False)
        self.assertHasMessage(response, FirstRunView.success_message)

        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertEqual(user.username, "admin")
        self.assertEqual(user.email, "admin@crazyarms.example")
        self.assertTrue(user.check_password("user-pw"))
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)

        self.assertEqual(config.STATION_NAME, "Test Station")
        self.assertEqual(config.ICECAST_ADMIN_PASSWORD, "icecast-pw")
        self.assertEqual(config.ICECAST_ADMIN_EMAIL, "admin@crazyarms.example")
        self.assertEqual(config.ICECAST_SOURCE_PASSWORD, "random-pw")
        self.assertEqual(config.ICECAST_RELAY_PASSWORD, "random-pw")

        self.assertEqual(UpstreamServer.objects.count(), 1)
        upstream = UpstreamServer.objects.get()
        self.assertEqual(upstream.name, "local-icecast")
        self.assertEqual(upstream.hostname, "icecast")
        self.assertEqual(upstream.protocol, UpstreamServer.Protocol.HTTP)
        self.assertEqual(upstream.port, 8000)
        self.assertEqual(upstream.username, "source")
        self.assertEqual(upstream.password, "random-pw")
        self.assertEqual(upstream.mount, "live")
        self.assertEqual(upstream.encoding, UpstreamServer.Encoding.MP3)
        self.assertIsNone(upstream.bitrate)
        self.assertEqual(upstream.mime, "")
        self.assertIsNone(upstream.encoding_args)

        # TODO: this should be tested in whatever tests services/services.py
        for config_file in (
            "icecast/icecast.xml",
            "harbor/harbor.liq",
            "harbor/supervisor/harbor.conf",
            "harbor/supervisor/pulseaudio.conf",
            "upstream/local-icecast.liq",
            "upstream/supervisor/local-icecast.conf",
            "zoom/supervisor/xvfb-icewm.conf",
            "zoom/supervisor/x11vnc.conf",
            "zoom/supervisor/websockify.conf",
        ):
            self.assertTrue(
                os.path.exists(f"/config/{config_file}"),
                f"Config file {config_file} doesn't exist.",
            )

        supervisor_start_calls = [set(c.args[1:]) for c in supervisor_mock.call_args_list if c.args[0] == "start"]
        self.assertIn({"xvfb-icewm", "x11vnc", "websockify"}, supervisor_start_calls)
        self.assertIn({"harbor", "pulseaudio"}, supervisor_start_calls)
        self.assertIn({"local-icecast"}, supervisor_start_calls)

        self.assertEqual(AudioAsset.objects.count(), 75)
        self.assertEqual(Rotator.objects.count(), 3)
        self.assertEqual(Playlist.objects.count(), 1)
        self.assertEqual(Stopset.objects.count(), 3)
        self.assertEqual(StopsetRotator.objects.count(), 13)

    def test_redirects_when_user_exists(self):
        User.objects.create_user("user")
        response = self.client.get(reverse("first_run"))
        self.assertRedirects(response, reverse("status"), fetch_redirect_response=False)
