import json
import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from apps.tables.forms import SalesForm
from apps.common.models import Sales
from apps.tables.models import HideShowFilter, ModelFilter, PageItems
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib.auth.decorators import login_required
from apps.tables.utils import product_filter
from django.conf import settings
from apps.tables.models import ModelChoices
from django.urls import reverse
from django.views import View

# Create your views here.


def create_filter(request):
    if request.method == "POST":
        keys = request.POST.getlist('key')
        values = request.POST.getlist('value')
        for i in range(len(keys)):
            key = keys[i]
            value = values[i]

            ModelFilter.objects.update_or_create(
                parent=ModelChoices.SALES,
                key=key,
                defaults={'value': value}
            )

        return redirect(request.META.get('HTTP_REFERER'))

def create_page_items(request):
    if request.method == 'POST':
        items = request.POST.get('items')
        page_items, created = PageItems.objects.update_or_create(
            parent=ModelChoices.SALES,
            defaults={'items_per_page':items}
        )
        return redirect(request.META.get('HTTP_REFERER'))

def create_hide_show_filter(request):
    if request.method == "POST":
        data_str = list(request.POST.keys())[0]
        data = json.loads(data_str)

        HideShowFilter.objects.update_or_create(
            parent=ModelChoices.SALES,
            key=data.get('key'),
            defaults={'value': data.get('value')}
        )

        response_data = {'message': 'Model updated successfully'}
        return JsonResponse(response_data)

    return JsonResponse({'error': 'Invalid request'}, status=400)

def delete_filter(request, id):
    filter_instance = ModelFilter.objects.get(id=id, parent=ModelChoices.SALES)
    filter_instance.delete()
    return redirect(request.META.get('HTTP_REFERER'))

def datatables(request):
    db_field_names = [field.name for field in Sales._meta.get_fields()]

    # hide show column
    field_names = []
    for field_name in db_field_names:
        fields, created = HideShowFilter.objects.get_or_create(key=field_name, parent=ModelChoices.SALES)
        field_names.append(fields)

    # model filter
    filter_string = {}
    filter_instance = ModelFilter.objects.filter(parent=ModelChoices.SALES)
    for filter_data in filter_instance:
        filter_string[f'{filter_data.key}__icontains'] = filter_data.value

    order_by = request.GET.get('order_by', 'ID')
    queryset = Sales.objects.filter(**filter_string).order_by(order_by)
    product_list = product_filter(request, queryset, db_field_names)
    form = SalesForm()

    # pagination
    page_items = PageItems.objects.filter(parent=ModelChoices.SALES).last()
    items = 25
    if page_items:
        items = page_items.items_per_page

    page = request.GET.get('page', 1)
    paginator = Paginator(product_list, items)

    try:
        sales = paginator.page(page)
    except PageNotAnInteger:
        return redirect(reverse('data_tables"'))
    except EmptyPage:
        return redirect(reverse('data_tables"'))

    # submit data
    if request.method == 'POST':
        form = SalesForm(request.POST)
        if form.is_valid():
            return post_request_handling(request, form)
    
    read_only_fields = ('id', )

    context = {
        'segment'  : 'tables',
        'parent'   : 'apps',
        'form'     : form,
        'sales' : sales,
        'total_items': Sales.objects.count(),
        'db_field_names': db_field_names,
        'field_names': field_names,
        'filter_instance': filter_instance,
        'read_only_fields': read_only_fields,
        'items': items
    }
    
    return render(request, 'pages/apps/datatables.html', context)



@login_required(login_url='/accounts/login-v1/')
def post_request_handling(request, form):
    form.save()
    return redirect(request.META.get('HTTP_REFERER'))

@login_required(login_url='/accounts/login-v1/')
def delete(request, id):
    sale = Sales.objects.get(ID=id)
    sale.delete()
    return redirect(request.META.get('HTTP_REFERER'))


@login_required(login_url='/accounts/login-v1/')
def update(request, id):
    sales = Sales.objects.get(ID=id)
    if request.method == 'POST':
        for attribute, value in request.POST.items():
            if attribute == 'csrfmiddlewaretoken':
                continue

            if getattr(sales, attribute, value) is not None:
                setattr(sales, attribute, value)
        
        sales.save()

    return redirect(request.META.get('HTTP_REFERER'))



# Export as CSV
class ExportCSVView(View):
    def get(self, request):
        db_field_names = [field.name for field in Sales._meta.get_fields()]
        fields = []
        show_fields = HideShowFilter.objects.filter(value=False, parent=ModelChoices.SALES)
        for field in show_fields:
            fields.append(field.key)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products.csv"'

        writer = csv.writer(response)
        writer.writerow(fields) 

        filter_string = {}
        filter_instance = ModelFilter.objects.filter(parent=ModelChoices.SALES)
        for filter_data in filter_instance:
            filter_string[f'{filter_data.key}__icontains'] = filter_data.value

        order_by = request.GET.get('order_by', 'ID')
        queryset = Sales.objects.filter(**filter_string).order_by(order_by)

        products = product_filter(request, queryset, db_field_names)

        for product in products:
            row_data = [getattr(product, field) for field in fields]
            writer.writerow(row_data)

        return response