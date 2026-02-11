from django import template

register = template.Library()


@register.filter(name="replace_value")
def replace_value(value, arg):
    """Replace the delimiter with spaces and title-case the label."""
    return value.replace(arg, " ").title()
