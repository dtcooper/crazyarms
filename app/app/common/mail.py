import logging

from django.contrib import messages
from django.core.mail import send_mail as django_send_mail

logger = logging.getLogger(f"crazyarms.{__name__}")


def send_mail(recipient, subject, body, request=None):
    try:
        django_send_mail(subject=subject, message=body, from_email=None, recipient_list=[recipient])
    except Exception as e:
        logger.error(f'An error occurred while sending mail "{subject}" to {recipient}: {e}')
        if request:
            messages.error(
                request,
                "An error occurred while sending email. Message not sent. Try again.",
            )
        return False
    return True
