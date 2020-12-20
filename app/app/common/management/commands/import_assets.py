import argparse
import logging
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from autodj.models import AudioAsset, Playlist, RotatorAsset
from broadcast.models import BroadcastAsset
from common.models import User


logger = logging.getLogger(f'carb.{__name__}')


class Command(BaseCommand):
    help = 'Import Audio Files'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', type=str, help="path(s) of audio assets (or folders) in `imports/' "
                                                               'folder, with that portion of the path omitted.')
        parser.add_argument('-u', '--username', help='Username of uploader (can be left blank)')
        group = parser.add_mutually_exclusive_group()
        group.add_argument('-p', '--playlist', help='Add to playlist by name. (Audio assets only)')
        group.add_argument('-P', '--create-playlist', help="Add to playlist by name, creating it if it doesn't exist")
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--audio-assets', action='store_true', help='Import audio assets (the default behaviour)')
        group.add_argument('--rotator-assets', action='store_true', help='Import rotator assets')
        group.add_argument('--scheduled-broadcast-assets', action='store_true',
                           help='Import scheduled broadcast assets')
        parser.add_argument('-d', '--delete', action='store_true', help=(
            'Delete input files, whether the can be converted to audio files or not (path still normalized).'))
        parser.add_argument('--audio-imports-root', help=argparse.SUPPRESS, default=settings.AUDIO_IMPORTS_ROOT)
        parser.add_argument('--dont-print', action='store_true', help=argparse.SUPPRESS)

    def log(self, s, *args, **kwargs):
        if self.dont_print:
            logger.info(s)
        else:
            print(s, *args, **kwargs)

    def handle(self, *args, **options):
        self.dont_print = options['dont_print']
        if not self.dont_print and options['verbosity'] < 2:
            logging.disable(logging.WARNING)

        uploader = playlist = None
        if options['playlist'] or options['create_playlist']:
            if options['rotator_assets'] or options['prerecorded_broadcast_assets']:
                self.log("Can't add that type of asset to a playlist")
                return

            name = options['playlist'] or options['create_playlist']

            try:
                playlist = Playlist.objects.get(name__iexact=name)
            except Playlist.DoesNotExist:
                if options['playlist']:
                    self.log(f'No playlist exists with name {name}. Exiting.')
                    self.log('Try one of: ')
                    for name in Playlist.objects.values_list('name', flat=True).order_by('name'):
                        self.log(f' * {name}')
                else:
                    self.log(f'Playlist {name} does not exist. Creating it.')
                    playlist = Playlist.objects.create(name=name)

        if options['username']:
            try:
                if options['username'].startswith('id='):
                    uploader = User.objects.get(id=options['username'].removeprefix('id='))
                else:
                    uploader = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                self.log(f'No user exists with username {options["username"]}. Skipping.')

        if options['rotator_assets']:
            asset_cls = RotatorAsset
        elif options['scheduled_broadcast_assets']:
            asset_cls = BroadcastAsset
        else:
            asset_cls = AudioAsset

        audio_imports_root = options['audio_imports_root']
        asset_paths = []

        for path in options['paths']:
            if path in ('.', 'imports'):
                path = ''

            imports_root_path = f'{audio_imports_root}{path}'
            if path.startswith('imports/') and not os.path.exists(imports_root_path):
                imports_root_path = f'{audio_imports_root}{path.removeprefix("imports/")}'

            if os.path.isfile(imports_root_path):
                asset_paths.append(imports_root_path)

            elif os.path.isdir(imports_root_path):
                imports_root_path = imports_root_path.removesuffix('/')
                for root, dirs, files in os.walk(imports_root_path):
                    for file in files:
                        full_path = f'{root}/{file}'
                        if os.path.isfile(full_path) and not os.path.islink(full_path):
                            asset_paths.append(full_path)

        asset_paths.sort()

        if asset_paths:
            self.log(f'Found {len(asset_paths)} potential asset files in paths under imports/. Running.')
        else:
            self.log('Found no potential assets found with the supplied paths under imports/. Exiting.')
            return

        for path in asset_paths:
            delete_str = 'and deleting ' if options['delete'] else ''
            self.log(f'Importing {delete_str}{path.removeprefix(audio_imports_root)}', end='', flush=True)

            asset = asset_cls(uploader=uploader, file_basename=os.path.basename(path))
            asset.file.save(f'imported/{asset.file_basename}', File(open(path, 'rb')), save=False)

            try:
                asset.clean()
            except ValidationError as e:
                self.log(f'... skipping, validation error: {e.message}')
            else:
                asset.save()
                if playlist:
                    asset.playlists.add(playlist)
                self.log('... done!')
            finally:
                if options['delete']:
                    os.remove(path)
