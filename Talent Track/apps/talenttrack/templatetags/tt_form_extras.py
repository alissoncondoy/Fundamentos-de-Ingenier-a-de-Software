from django import template

register = template.Library()


@register.filter(name="tt_field")
def tt_field(form, name):
    """Safe access to a bound field by name.

    Django templates don't support bracket notation like form[name].
    This filter allows: {{ form|tt_field:name }}
    """
    try:
        return form[name]
    except Exception:
        return None
