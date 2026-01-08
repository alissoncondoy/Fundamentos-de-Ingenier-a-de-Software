from django.urls import path

from . import views

urlpatterns = [
    path("", views.datatables, name="data_tables"),
    path('create-filter/', views.create_filter, name="create_filter"),
    path('create-page-items/', views.create_page_items, name="create_page_items"),
    path('create-hide-show-items/', views.create_hide_show_filter, name="create_hide_show_filter"),
    path('delete-filter/<int:id>/', views.delete_filter, name="delete_filter"),
    path('delete/<int:id>/', views.delete, name="delete"),
    path('update/<int:id>/', views.update, name="update"),

    path('export-csv/', views.ExportCSVView.as_view(), name='export_csv'),
]