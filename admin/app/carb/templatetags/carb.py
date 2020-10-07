from django import template


register = template.Library()


@register.filter
def boolstr(value):
    return 'true' if value else 'false'
