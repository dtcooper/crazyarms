#!/usr/bin/env python3

import argparse
from collections import OrderedDict
import datetime
import json
import pickle
import pprint
import os
import sys

from dateutil.parser import parse as dateutil_parse
import gspread
from gspread_formatting import cellFormat, color, format_cell_ranges
from oauth2client.service_account import ServiceAccountCredentials
import pytz


SHEET_TIMEZONE = pytz.timezone('US/Pacific')
USER_DATA_CACHE_FILE = os.path.join(os.path.dirname(__file__), 'user-data.pkl')
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), 'credentials.json')
if not os.path.exists(CREDENTIALS_FILE):
    print(f'No Google credentials file found at {CREDENTIALS_FILE}. Exiting.')
    sys.exit(1)


def sanitize_password(password):  # Must match sanitize_password() code in harbor.liq
    return password.lower().strip()


def get_and_cache_user_data(sheet_key, cache=True):
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/drive',
    ])
    client = gspread.authorize(creds)
    data = OrderedDict()

    sheet = client.open_by_key(sheet_key).sheet1
    rows = sheet.get_all_values()

    headers = ('name', 'start', 'end', 'password', 'email')
    for header_row, row in enumerate(rows):
        if all(header in row[column].lower() for column, header in enumerate(headers)):
            break
    else:
        print("Couldn't find header row.")
        sys.exit(1)

    bad_sheet_rows = set()
    for sheet_row, (name, start, end, password, email, *_) in enumerate(rows[header_row + 1:], header_row + 2):
        if all(map(lambda s: s.strip(), (name, start, end, password))):
            try:
                start = SHEET_TIMEZONE.localize(dateutil_parse(start))
                end = SHEET_TIMEZONE.localize(dateutil_parse(end))
            except ValueError:
                pass
            else:
                password = sanitize_password(password)
                if password:
                    data[password] = OrderedDict((('name', name.strip()), ('email', email.strip()),
                                                  ('start', start), ('end', end)))
                    continue
        bad_sheet_rows.add(sheet_row)

    # +1 from header, also gspread is 1-offset, not 0-offset = +2
    green_fmt = cellFormat(backgroundColor=color(0.9, 1, 0.9))
    red_fmt = cellFormat(backgroundColor=color(1, 0.9, 0.9))
    format_cell_ranges(sheet, [
        # +1 from header, also gspread is 1-offset, not 0-offset = +2
        (str(r), red_fmt if r in bad_sheet_rows else green_fmt)
        for r in range(header_row + 2, sheet_row + 1)
    ])

    if cache:
        with open(USER_DATA_CACHE_FILE, 'wb') as cache_file:
            pickle.dump(data, cache_file)

    return data


def auth_data(user_data, password, date, entry_grace=0, exit_grace=0):
    password = sanitize_password(password)
    data = OrderedDict((('currently_authorized', False), ('valid_user', False), ('password_sanitized', password)))

    user_data = user_data.get(password)
    if user_data is not None:
        data['valid_user'] = True
        for key, value in user_data.items():
            data[key] = str(value)
        start = user_data['start'] - datetime.timedelta(seconds=entry_grace)
        end = user_data['end'] + datetime.timedelta(seconds=exit_grace)
        data['start_with_grace_period'], data['end_with_grace_period'] = str(start), str(end)
        data['currently_authorized'] = start <= date <= end
        data['end_with_grace_period_unix'] = str(end.timestamp())

    return data


def main():
    parser = argparse.ArgumentParser(description='harbor authentication script')
    parser.add_argument('password', help='password to check (if left blank, download and cache)', nargs='?')
    parser.add_argument('-k', '--sheet-key', help='google sheet key', required=True)
    parser.add_argument('--timezone', help='timezone (default: US/Pacific)', default='US/Pacific')
    parser.add_argument('-d', '--date', help='date and time to check (default: now)')
    parser.add_argument('-f', '--force', action='store_true', help="force a download when checking password (don't use cache)")
    parser.add_argument('-B', '--grace-period-entry', type=int, default=90, help='entry grace period in seconds (default: 90)')
    parser.add_argument('-A', '--grace-period-exit', type=int, default=5, help='exit grace period in seconds (default: 5)')
    parser.add_argument('--dump', action='store_true', help='dump all user data')

    args = parser.parse_args()

    if args.force or args.password is not None or not os.path.exists(USER_DATA_CACHE_FILE):
        user_data = get_and_cache_user_data(sheet_key=args.sheet_key)
    else:
        with open(USER_DATA_CACHE_FILE, 'rb') as cache_file:
            user_data = pickle.load(cache_file)

    if args.dump:
        pprint.pprint(user_data)
    elif args.password is not None:
        timezone = pytz.timezone(args.timezone)
        if args.date:
            date = timezone.localize(dateutil_parse(args.date, fuzzy=True).replace(tzinfo=None))
        else:
            date = datetime.datetime.now(timezone)

        data = auth_data(user_data=user_data, password=args.password, date=date,
                         entry_grace=args.grace_period_entry, exit_grace=args.grace_period_exit)
        print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
