#!/bin/sh
"true" '''\'
VENV_PYTHON=$(dirname "$0")/venv/bin/python

if [ -x $VENV_PYTHON ]; then
    exec $VENV_PYTHON "$0" "$@"
else
    exec python3 "$0" "$@"
fi
'''

import argparse
from collections import OrderedDict
import datetime
import json
import os
import sys

from dateutil.parser import parse as dateutil_parse
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pytz


SHEET_TIMEZONE = pytz.timezone('US/Pacific')
AUTH_DATA_FILE = os.path.join(os.path.dirname(__file__), 'auth-data.json')
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
if not os.path.exists(CREDENTIALS_FILE):
    print(f'No Google credentials file found at {CREDENTIALS_FILE}. Exiting.')
    sys.exit(1)


def sanitize_password(password):
    return password.lower().strip()


def cache_auth_data(sheet_key):
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/drive',
    ])
    client = gspread.authorize(creds)
    auth_data = OrderedDict()

    sheet = client.open_by_key(sheet_key)
    schedule, passwords = sheet.worksheets()
    schedule_rows = schedule.get_all_values()
    password_rows = passwords.get_all_values()

    assert schedule_rows[1] == ['DJ Name', 'Show Start (Pacific Time)', 'Show End (Pacific Time)']
    assert password_rows[0] == ['DJ Name', 'Password', 'Email']
    for (dj_name_schedule, start, end), (dj_name_password, password, _) in zip(
        schedule_rows[2:], password_rows[1:]
    ):
        assert dj_name_schedule == dj_name_password
        auth_data[sanitize_password(password)] = (dj_name_schedule, start, end)

    with open(AUTH_DATA_FILE, 'w') as auth_file:
        json.dump(auth_data, auth_file, indent=2)

    return auth_data


def authorize_data(auth_data, password, date, grace=None):
    data = {
        'authorized': False,
        'valid_user': False,
    }

    user_data = auth_data.get(sanitize_password(password))
    if user_data is not None:
        dj_name, start, end = user_data
        data.update({'valid_user': True, 'name': dj_name, 'start': start, 'end': end})

        start, end = map(lambda s: SHEET_TIMEZONE.localize(dateutil_parse(s)), (start, end))
        if grace is not None:
            start -= datetime.timedelta(seconds=grace)
            end += datetime.timedelta(seconds=grace)

        data['authorized'] = start <= date <= end
        data['seconds_to_kick'] = round((end - date).total_seconds()) if data['authorized'] else -1

    return data


def main():
    parser = argparse.ArgumentParser(description='harbor authentication script')
    parser.add_argument('password', help='password to check (if left blank, download and cache)', nargs='?')
    parser.add_argument('-k', '--sheet-key', help='google sheet key', required=True)
    parser.add_argument('--timezone', help='timezone (default: US/Pacific)', default='US/Pacific')
    parser.add_argument('-d', '--date', help='date and time to check (default: now)')
    parser.add_argument('-f', '--force', help="force a download when checking password (don't use cache)")
    parser.add_argument('-g', '--grace-period', type=int, default=90, help='grace period in seconds (default: 90)')

    args = parser.parse_args()

    if args.force or not args.password or not os.path.exists(AUTH_DATA_FILE):
        auth_data = cache_auth_data(sheet_key=args.sheet_key)
    else:
        with open(AUTH_DATA_FILE, 'r') as auth_file:
            auth_data = json.load(auth_file)

    if args.password:
        timezone = pytz.timezone(args.timezone)
        if args.date:
            date = timezone.localize(dateutil_parse(args.date, fuzzy=True).replace(tzinfo=None))
        else:
            date = datetime.datetime.now(timezone)

        data = authorize_data(auth_data=auth_data, password=args.password, date=date, grace=args.grace_period)
        print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
