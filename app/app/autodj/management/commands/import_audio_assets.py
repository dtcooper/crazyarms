import logging  # TODO disable logging
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from autodj.models import AudioAsset, Playlist
from common.models import User


class Command(BaseCommand):
    help = 'Import Audio Assets Files'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', type=str, help="path(s) of audio assets (or folders) in `media/' "
                                                               'folder, with that portion of the path omitted.')
        parser.add_argument('-u', '--username', help='Username of uploader (can be left blank)')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-p', '--playlist', help='Add to existing playlist by name')
        group.add_argument('-P', '--create-playlist', help="Add to playlist by name, creating it if it doesn't exist")
        parser.add_argument('-d', '--dedupe', action='store_true', help=(
            'Attempt to de-dupe by not saving assets with the same artist, album, and title as an existing one. '
            '(Artist and title must exist.)'))

    def handle(self, *args, **options):
        uploader = playlist = None
        if options['username']:
            try:
                uploader = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                print(f'No user exists with username {options["username"]}. Exiting.')
                return

        if options['playlist'] or options['create_playlist']:
            name = options['playlist'] or options['create_playlist']

            try:
                playlist = Playlist.objects.get(name__iexact=name)
            except Playlist.DoesNotExist:
                if options['playlist']:
                    print(f'No playlist exists with name {name}. Exiting.')
                    print('Try one of: ')
                    for name in Playlist.objects.values_list('name', flat=True).order_by('name'):
                        print(f' * {name}')
                else:
                    print(f'Playlist {name} does not exist. Creating it.')
                    playlist = Playlist.objects.create(name=name)

        asset_paths = []

        for path in options['paths']:
            media_root_path = f'{settings.MEDIA_ROOT}{path}'
            if os.path.isfile(media_root_path):
                asset_paths.append(path)

            elif os.path.isdir(media_root_path):
                for root, dirs, files in os.walk(media_root_path):
                    for file in files:
                        full_asset_path = os.path.join(root, file)
                        if os.path.isfile(full_asset_path) and not os.path.islink(full_asset_path):
                            asset_paths.append(full_asset_path.removeprefix(settings.MEDIA_ROOT))

        if asset_paths:
            print(f'Found {len(asset_paths)} potential asset files in paths under {settings.MEDIA_ROOT}. Running.')
        else:
            print(f'Found no potential assets in paths under {settings.MEDIA_ROOT}. Exiting.')
            return

        for asset_path in asset_paths:
            print(f'Importing {asset_path}', end='', flush=True)

            audio_asset = AudioAsset(file=asset_path, uploader=uploader)

            try:
                audio_asset.clean()
            except ValidationError as e:
                print(f'... skipping, validation error: {e.message}')
                continue

            audio_asset.pre_save()

            if options['dedupe']:
                if (
                    audio_asset.title_normalized and audio_asset.artist_normalized
                    and AudioAsset.objects.filter(artist_normalized=audio_asset.artist_normalized,
                                                  album_normalized=audio_asset.album_normalized,
                                                  title_normalized=audio_asset.title_normalized).exists()
                ):
                    print('... skipping, found an existing asset with the same artist, album, and title')
                    continue

            if not audio_asset.file:
                print('... skipping, invalid file')
                continue

            audio_asset.save(run_pre_save=False)
            if playlist:
                audio_asset.playlists.add(playlist)
            print('... imported!')

        print()
