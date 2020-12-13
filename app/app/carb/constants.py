import os


CACHE_KEY_ASSET_TASK_LOG_PREFIX = 'asset:task-log:'  # + task.id
CACHE_KEY_YTDL_UP2DATE = f'youtube-dl:up2date:{"tasks" if  os.environ.get("RUN_HUEY") else "app"}'
CACHE_KEY_GCAL_LAST_SYNC = 'gcal:last-sync'
CACHE_KEY_HARBOR_CONFIG_CONTEXT = 'harbor:config-context'
CACHE_KEY_HARBOR_BAN_PREFIX = 'harbor:ban:'  # + user.id
CACHE_KEY_AUTODJ_NO_REPEAT_IDS = 'autodj:no-repeat-ids'
CACHE_KEY_AUTODJ_NO_REPEAT_ARTISTS = 'autodj:no-repeat-artists'
CACHE_KEY_AUTODJ_CURRENT_STOPSET = 'autodj:current-stopset'
CACHE_KEY_AUTODJ_STOPSET_LAST_FINISHED_AT = 'autodj:stopset-last-finished-at'
REDIS_KEY_ROOM_INFO = 'zoom-runner:room-info'
