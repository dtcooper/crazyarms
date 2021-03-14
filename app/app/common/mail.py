import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail as django_send_mail

from constance import config

logger = logging.getLogger(f"crazyarms.{__name__}")


def send_mail(recipient, subject, body, request=None):
    from_email = f'"{config.STATION_NAME} Admin" <no-reply@{settings.DOMAIN_NAME}>'

    try:
        django_send_mail(subject=subject, message=body, from_email=from_email, recipient_list=[recipient])
    except Exception as e:
        logger.exception(f'An error occurred while sending mail "{subject}" to {recipient}: {e}')
        if request:
            messages.error(
                request,
                "An error occurred while sending email. Message not sent. Try again.",
            )
        return False
    return True
