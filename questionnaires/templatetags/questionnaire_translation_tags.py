from django import template

register = template.Library()


@register.filter
def get_item(value, key):
    """Read canonical-keyed translation maps and position-indexed label lists."""
    if isinstance(value, dict):
        return value.get(str(key))
    if isinstance(value, list):
        try:
            return value[int(key)]
        except (TypeError, ValueError, IndexError):
            return None
    return None
