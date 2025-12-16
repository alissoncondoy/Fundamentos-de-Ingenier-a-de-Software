from django.urls import path
from home import views
from django.contrib.auth import views as auth_views


urlpatterns = [
  # Dashboard
  path('', views.default, name="index"),
  path('automotive', views.automotive, name="automotive"),
  path('smart-home', views.smart_home, name="smart_home"),
  path('crm', views.crm, name="crm"),
  # Dashboard -> VR
  path('vr/vr-default/', views.vr_default, name="vr_default"),
  path('vr/vr-info/', views.vr_info, name="vr_info"),

  # Pages
  path('pages/messages/', views.messages, name="messages"),
  path('pages/widgets/', views.widgets, name="widgets"),
  path('pages/charts/', views.charts, name="charts"),
  path('pages/sweet-alerts/', views.sweet_alerts, name="sweet_alerts"),
  path('pages/notifications/', views.notifications, name="notifications"),
  path('pages/pricing-page/', views.pricing_page, name="pricing"),
  path('pages/rtl/', views.rtl, name="rtl"),
  # Pages -> Profile
  path('pages/profile/profile-overview/', views.profile_overview, name="profile_overview"), 
  path('pages/profile/teams/', views.teams, name="teams"), 
  path('pages/profile/projects/', views.projects, name="projects"), 
  # Pages -> Users
  path('pages/users/reports/', views.reports, name="reports"),
  path('pages/users/new-user/', views.new_user, name="new_user"),
  # Pages -> Accounts
  path('pages/accounts/settings/', views.settings, name="settings"),
  path('pages/accounts/billing/', views.billing, name="billing"),
  path('pages/accounts/invoice/', views.invoice, name="invoice"),
  path('pages/accounts/security/', views.security, name="security"),
  # Pages -> Porjects
  path('pages/projects/general/', views.general, name="general"),
  path('pages/projects/timeline/', views.timeline, name="timeline"),
  path('pages/projects/new-project/', views.new_project, name="new_project"),

  # Applications
  path('applications/kanban/', views.kanban, name="kanban"),
  path('applications/wizard/', views.wizard, name="wizard"),
  path('applications/datatables/', views.datatables, name="datatables"),
  path('applications/calendar/', views.calendar, name="calendar"),
  path('applications/analytics/', views.analytics, name="analytics"),

  # Ecommerce
  path('ecommerce/overview/', views.overview, name="overview"),
  path('ecommerce/referral/', views.referral, name="referral"),
  # Ecommerce -> Products
  path('ecommerce/products/new-product/', views.new_product, name="new_product"),
  path('ecommerce/products/edit-product/', views.edit_product, name="edit_product"),
  path('ecommerce/products/product-page/', views.product_page, name="product_page"),
  path('ecommerce/products/products-list/', views.products_list, name="products_list"),
  # Ecommerce -> Orders
  path('ecommerce/orders/order-list', views.order_list, name="order_list"),
  path('ecommerce/orders/order-details', views.order_details, name="order_details"),

  # Authentication -> Register
  path('accounts/register/basic-register/', views.basic_register, name="basic_register"),
  path('accounts/register/cover-register/', views.cover_register, name="cover_register"),
  path('accounts/register/illustration-register/', views.illustration_register, name="illustration_register"),
  # Authentication -> Login
  path('accounts/login/basic-login/', views.BasicLoginView.as_view(), name="basic_login"),
  path('accounts/login/cover-login/', views.CoverLoginView.as_view(), name="cover_login"),
  path('accounts/login/illustration-login/', views.IllustrationLoginView.as_view(), name="illustration_login"),
  # Authentication -> Reset
  path('accounts/reset/basic-reset/', views.BasicResetView.as_view(), name="basic_reset"),
  path('accounts/reset/cover-reset/', views.CoverResetView.as_view(), name="cover_reset"),
  path('accounts/reset/illustration-reset/', views.IllustrationResetView.as_view(), name="illustration_reset"),

  path('accounts/password-change/', views.UserPasswordChangeView.as_view(), name='password_change'),
  path('accounts/password-change-done/', auth_views.PasswordChangeDoneView.as_view(
      template_name='accounts/done/change-done.html'
  ), name="password_change_done"),
  path('accounts/password-reset-done/', auth_views.PasswordResetDoneView.as_view(
      template_name='accounts/done/basic.html'
  ), name='password_reset_done'),
  path('accounts/password-reset-confirm/<uidb64>/<token>/', 
      views.UserPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
  path('accounts/password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
      template_name='accounts/complete/basic.html'
  ), name='password_reset_complete'),

  # Authentication -> Lock
  path('accounts/lock/basic-lock/', views.basic_lock, name="basic_lock"),
  path('accounts/lock/cover-lock/', views.cover_lock, name="cover_lock"),
  path('accounts/lock/illustration-lock/', views.illustration_lock, name='illustration_lock'),
  # Authentication -> Verification
  path('accounts/verification/basic-verification/', views.basic_verification, name="basic_verification"),
  path('accounts/verification/cover-verification/', views.cover_verification, name="cover_verification"),
  path('accounts/verification/illustration-verification/', views.illustration_verification, name="illustration_verification"),
  # Error
  path('error/404/', views.error_404, name="error_404"),
  path('error/500/', views.error_500, name="error_500"),
  path('logout/', views.logout_view, name="logout"),
]
