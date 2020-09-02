#!/usr/bin/env python3

import argparse
import getpass
import os
import smtplib
import sys
import time

sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'harbor'))
from auth import get_and_cache_user_data

USERNAME = 'david.cooper@burningman.org'
SENDER = f'"David Cooper" <{USERNAME}>'
STRFTME_FMT = '%A %B %-d, %Y %-I:%M %p (%-H:%M) Pacific Time (PDT) (GMT%z)'


def email(user):
    start, end = map(lambda d: d.strftime(STRFTME_FMT), (user['start'], user['end']))
    return f'''To: {user["email"]}\r
From: {SENDER}\r
Subject: [IMPORTANT] BMIR Broadcast Stream Info 2020\r\n\r
Hi {user["name"]},

Here's the information you'll need to broadcast to BMIR this year. (You can
ignore the Icecast password if you're planning on using Zoom.)

Show Start Time: {start}
Show End Time: {end}

Icecast Password: {user["password"]}

You will be able to log in to Icecast up to 90 seconds before your show provided
the previous DJ has logged off. Please log off on time, but you will be booted
after a 90 second grace period when your slot is up.

Streaming Guide: https://bmir.org/streaming-guide-2020
Schedule: https://bmir.org/schedule-2020

Any questions, please reply to this email.

Thanks and have fun,

David'''


def main():
    parser = argparse.ArgumentParser(description='single-user email blast script (GMail only)')
    parser.add_argument('-k', '--sheet-key', help='google sheet key', required=True)
    parser.add_argument('-p', '--print-emails', action='store_true', help="print emails (don't send them)")
    parser.add_argument('-o', '--only-user', help='send an email to this DJ name only')
    args = parser.parse_args()

    users = []
    for password, user in get_and_cache_user_data(args.sheet_key, cache=False).items():
        user = dict(user)
        user['password'] = password
        users.append(user)

    for user in list(users):
        if not user['email'].strip():
            print(f'WARNING: Skipping user {user["name"]} who has no email address')
            users.remove(user)

    if args.only_user:
        for user in users:
            if user['name'].strip().lower() == args.only_user.strip().lower():
                users = [user]
                break
        else:
            parser.error(f'DJ name "{args.only_user}" does not exist in spreadsheet')

    if args.print_emails:
        for user in users:
            print('=' * 40)
            print(email(user))
        print('=' * 40)
    else:
        password = getpass.getpass('GMail Password: ')

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(USERNAME, password)

        for user in users:
            server.sendmail(SENDER, user['email'], email(user))
            print(f'Sent to: {user["name"]} // {user["email"]}')
            time.sleep(1)


if __name__ == '__main__':
    main()
