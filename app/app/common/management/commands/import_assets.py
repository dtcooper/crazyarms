import logging
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand

from autodj.models import AudioAsset, Playlist, RotatorAsset
from broadcast.models import BroadcastAsset
from common.models import User

logger = logging.getLogger(f"carb.{__name__}")


class Command(BaseCommand):
    help = "Import Audio Files"

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="+",
            type=str,
            help="path(s) of audio assets (or folders) in `imports/' folder, with that portion of the path omitted.",
        )
        parser.add_argument("-u", "--username", help="Username of uploader (can be left blank)")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("-p", "--playlist", help="Add to playlist by name. (Audio assets only)")
        group.add_argument(
            "-P",
            "--create-playlist",
            help="Add to playlist by name, creating it if it doesn't exist",
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--audio-assets",
            action="store_true",
            help="Import audio assets (the default behaviour)",
        )
        group.add_argument("--rotator-assets", action="store_true", help="Import rotator assets")
        group.add_argument(
            "--scheduled-broadcast-assets",
            action="store_true",
            help="Import scheduled broadcast assets",
        )
        parser.add_argument(
            "-d",
            "--delete",
            action="store_true",
            help="Delete input files, whether the can be converted to audio files or not (path still normalized).",
        )

    def log(self, s, *args, **kwargs):
        if self.dont_print:
            logger.info(s)
        else:
            print(s, *args, **kwargs)

    def handle(self, *args, **options):
        if options["verbosity"] < 2:
            logging.disable(logging.WARNING)

        uploader = playlist = None
        if options["playlist"] or options["create_playlist"]:
            if options["rotator_assets"] or options["prerecorded_broadcast_assets"]:
                print("Can't add that type of asset to a playlist")
                return

            name = options["playlist"] or options["create_playlist"]

            try:
                playlist = Playlist.objects.get(name__iexact=name)
            except Playlist.DoesNotExist:
                if options["playlist"]:
                    print(f"No playlist exists with name {name}. Exiting.")
                    print("Try one of: ")
                    for name in Playlist.objects.values_list("name", flat=True).order_by("name"):
                        print(f" * {name}")
                else:
                    print(f"Playlist {name} does not exist. Creating it.")
                    playlist = Playlist.objects.create(name=name)

        if options["username"]:
            try:
                uploader = User.objects.get(username=options["username"])
            except User.DoesNotExist:
                print(f'No user exists with username {options["username"]}. Exiting.')
                return

        if options["rotator_assets"]:
            asset_cls = RotatorAsset
        elif options["scheduled_broadcast_assets"]:
            asset_cls = BroadcastAsset
        else:
            asset_cls = AudioAsset

        asset_paths = []

        for path in options["paths"]:
            if path in (".", "imports"):
                path = ""

            imports_root_path = f"{settings.AUDIO_IMPORTS_ROOT}{path}"
            if path.startswith("imports/") and not os.path.exists(imports_root_path):
                imports_root_path = f'{settings.AUDIO_IMPORTS_ROOT}{path.removeprefix("imports/")}'

            if os.path.isfile(imports_root_path):
                asset_paths.append(imports_root_path)

            elif os.path.isdir(imports_root_path):
                imports_root_path = imports_root_path.removesuffix("/")
                for root, dirs, files in os.walk(imports_root_path):
                    for file in files:
                        full_path = f"{root}/{file}"
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            asset_paths.append(full_path)

        asset_paths.sort()

        if asset_paths:
            print(f"Found {len(asset_paths)} potential asset files in paths under imports/. Running.")
        else:
            print("Found no potential assets found with the supplied paths under imports/. Exiting.")
            return

        for path in asset_paths:
            delete_str = "and deleting " if options["delete"] else ""
            print(
                f"Importing {delete_str}{path.removeprefix(settings.AUDIO_IMPORTS_ROOT)}",
                end="",
                flush=True,
            )

            asset = asset_cls(uploader=uploader, file_basename=os.path.basename(path))
            asset.file.save(f"imported/{asset.file_basename}", File(open(path, "rb")), save=False)

            try:
                asset.clean()
            except ValidationError as e:
                print(f"... skipping, validation error: {e}")
            else:
                asset.save()
                if playlist:
                    asset.playlists.add(playlist)
                print("... done!")
            finally:
                if options["delete"]:
                    os.remove(path)
