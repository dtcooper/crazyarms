#!/usr/bin/env bash

cd "$(dirname "$0")"

export_env_file () {
  set -a
  source "$1"
  set +a
}


# argparse() {
#     argparser=$(mktemp 2>/dev/null || mktemp -t argparser)
#     cat > "$argparser" <<EOF
# from __future__ import print_function
# import shlex
# import sys
# import argparse
# import os
# class MyArgumentParser(argparse.ArgumentParser):
#     def print_help(self, file=None):
#         """Print help and exit with error"""
#         super(MyArgumentParser, self).print_help(file=file)
#         sys.exit(1)
# parser = MyArgumentParser(prog=os.path.basename("$0"),
#             description="""$ARGPARSE_DESCRIPTION""")
# EOF

#     # stdin to this function should contain the parser definition
#     cat >> "$argparser"

#     cat >> "$argparser" <<EOF
# args = parser.parse_args()
# for arg in [a for a in dir(args) if not a.startswith('_')]:
#     key = arg.upper()
#     value = getattr(args, arg, None)
#     if isinstance(value, bool) or value is None:
#         print('{0}="{1}";'.format(key, 'yes' if value else ''))
#     else:
#         print('{0}="{1}";'.format(key, shlex.quote(value)))
# EOF

#     # Define variables corresponding to the options if the args can be
#     # parsed without errors; otherwise, print the text of the error
#     # message.
#     if python3 "$argparser" "$@" &> /dev/null; then
#         eval $(python3 "$argparser" "$@")
#         retval=0
#     else
#         python3 "$argparser" "$@"
#         retval=1
#     fi

#     rm "$argparser"
#     return $retval
# }

# argparse "$@" <<EOF || exit 1
# parser.add_argument('infile')
# parser.add_argument('outfile')
# parser.add_argument('-a', '--the-answer', default=42, type=int,
#                     help='Pick a number [default %(default)s]')
# parser.add_argument('-d', '--do-the-thing', action='store_true',
#                     default=False, help='store a boolean [default %(default)s]')
# parser.add_argument('-m', '--multiple', nargs='+',
#                     help='multiple values allowed')
# EOF
export_env_file env.default.vars

if [ -f env.vars ]; then
    export_env_file env.vars
fi

if [ "$USE_HTTPS" = 1 ]; then
    NGINX_COMPOSE_FILE=docker-compose.nginx-certbot.yml
else
    NGINX_COMPOSE_FILE=docker-compose.nginx.yml
fi

if [ "$#" = 0 ]; then
    CMD="up --remove-orphans"
else
    CMD="$@"
fi

set -x
docker-compose -f docker-compose.yml -f "$NGINX_COMPOSE_FILE" $CMD
