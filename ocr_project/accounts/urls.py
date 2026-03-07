from django.urls import path
from . import views


urlpatterns = [

    path("", views.loginview, name="login"),
    path("signup/", views.signup, name="signup"),
    path("reset-password/<uidb64>/<token>/", views.reset_password, name="password_reset_confirm"),
    path("logout/", views.logoutview, name="logout"),
    path("password-reset-sent/", views.password_reset_sent, name="password_reset_sent"),
    path("password-reset-done/", views.password_reset_done, name="password_reset_done"),
    path("password-reset-confirmation/", views.password_reset_sent, name="password_reset_confirmation"),
    path("superuser-dashboard/", views.superuser_dashboard, name="superuser_dashboard"),

    # GST Details Management
    path("edit-gst-detail/<int:gst_id>/", views.edit_gst_detail, name="edit_gst_detail"),
    path("delete-gst-detail/<int:gst_id>/", views.delete_gst_detail, name="delete_gst_detail"),

    # Dashboard
    path("user-dashboard/", views.user_dashboard, name="user_dashboard"),
    path("upload-invoice/", views.upload_invoice, name="upload_invoice"),
    path("update-invoice-status/<int:invoice_id>/", views.update_invoice_status, name="update_invoice_status"),


    # Download validation summary 
    path("download-validation-summary/<int:invoice_id>/", views.download_validation_summary, name="download_validation_summary"),



    # Edit Invoice 
    #path('invoice/<int:invoice_id>/edit/', views.edit_invoice, name='edit_invoice'),

    
    # Get Invoice Raw Data for Modal Popup
    path('invoice-raw-data/<int:invoice_id>/', views.get_invoice_raw_data, name='invoice_raw_data'),


]