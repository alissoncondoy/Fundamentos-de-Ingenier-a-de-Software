from django import template

register = template.Library()


@register.filter(name="getattribute")
def getattribute(value, arg):

    #print( ' > ' + str( type( value ) ) + ' -> ' + str( arg ) )

    try:
        return getattr(value, arg)
    except:
        return ''
