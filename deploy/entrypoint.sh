#!/bin/sh
set -eu

# Compile the catalog before migrations: Django stores permission names in the
# database when it creates them, using the model labels available at that time.
python manage.py compilemessages --locale ru
python manage.py migrate --noinput
python manage.py localize_permissions
python manage.py collectstatic --noinput

exec "$@"
