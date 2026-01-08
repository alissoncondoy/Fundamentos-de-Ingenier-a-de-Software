from django.db.models import Q

def product_filter(request, queryset, fields):
    value = request.GET.get('search')
    
    if value:
        dynamic_q = Q()
        for field in fields:
            dynamic_q |= Q(**{f'{field}__icontains': value})
        return queryset.filter(dynamic_q)

    return queryset