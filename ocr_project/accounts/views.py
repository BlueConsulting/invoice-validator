from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.tokens import default_token_generator, PasswordResetTokenGenerator
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.core.cache import cache
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import os
from .forms import SignupForm, GSTDetailsForm, UserManagementForm
from .models import CompanyDetails, Invoice, GSTDetails
import random 
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site
from decimal import Decimal, InvalidOperation
from datetime import datetime
from .tokens import custom_token_generator
from .utils import send_email
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from .models import Invoice
import json
from accounts.validations.invoice_mapper import run_dynamic_validations
from accounts.validations.invoice_mapper import call_ocr_api, map_api_data_to_invoice

# Step1 : before validation we must populate invoice model
from accounts.validations.data_gathering import api_response_test
from accounts.validations.invoice_mapper import map_api_data_to_invoice


# ====== Additional imports for data processing for modal popup for Address Matching and Invoice Calculation ===== #
import re 
from difflib import SequenceMatcher


User = get_user_model()



# Helper function to normalize and compare addresses for better matching in Account Check (Customer Address)
def normalize_address(text):
    if not text:
        return ""
    
    text = text.lower()
    text = re.sub(r'[^a-z0-9 ]', ' ', text) # Remove special characters
    text = re.sub(r'\s+', ' ', text)  # normalize spaces

    # remove meaningless words
    stop_words = {
        "road", "rd", "street", "st", "area", "village",
        "district", "state", "india", "none"
    }

    tokens = [w for w in text.split() if w not in stop_words]
    return " ".join(tokens)


# Helper function to calculate address match percentage for Account Check (Customer Address)
def address_match_percentage(addr1, addr2):
    addr1_norm = normalize_address(addr1)
    addr2_norm = normalize_address(addr2)

    if not addr1_norm or not addr2_norm:
        return 0
    
    return SequenceMatcher(None, addr1_norm, addr2_norm).ratio() * 100
    


# Signup View
@csrf_protect
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    company = form.save()


                    # Create the User entry
                    user = User.objects.create(
                        username=company.contact_person_name,
                        email=company.contact_person_email,
                        company_code=company,
                        role='SuperUser',
                    )
                    user.set_unusable_password()
                    user.save()
                    

                    # Send Reset Password Link
                    token = custom_token_generator.make_token(user)
                    uid = urlsafe_base64_encode(user.email.encode('utf-8'))
                    domain = request.get_host()
                    link = f"http://{domain}/reset-password/{uid}/{token}/"
                    
                    subject = "Set your password"
                    body = f'''
                        <html>
                            <body>
                                <p>Dear {company.contact_person_name},</p>
                                <p>Click the link below to reset your password:</p>
                                <p><a href="{link}" target="_blank">Reset Password</a></p>
                            </body>
                        </html>
                    '''
                    
                    # Send using SMTP with configured credentials from settings
                    send_email(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD,
                               company.contact_person_email, subject, body=body)

                    messages.success(request, 'Account created successfully! Check your email to set your password.')
                    return redirect('password_reset_sent')


            except Exception as e:
                print(f"Signup process failed: {str(e)}")
                messages.error(request, 'Signup failed. Please try again.')
                return render(request, 'signup.html', {'form': form})
        else:
            return render(request, 'signup.html', {'form': form})

    # Initial GET request → show signup form
    form = SignupForm()
    return render(request, 'signup.html', {'form': form})



# Password Reset View
@csrf_protect
def reset_password(request, uidb64, token):

    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        print(f"DEBUG: Decoded UID: {uid}")
        user = User.objects.get(email=uid)
        print(f"DEBUG: User found: {user.email}")
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        print(f"DEBUG: Error finding user: {e}")
        user = None

    if user:
        token_valid = custom_token_generator.check_token(user, token)
        print(f"DEBUG: Token valid: {token_valid}")
        if token_valid:
            if request.method == 'POST':
                new_password = request.POST.get('password')
                confirm_password = request.POST.get('confirm_password')
                
                # here we are checking for password match so on UI also there will be 2 fields 
                # 1st is password and 2nd is confirm password 
                if new_password == confirm_password:
                    user.set_password(new_password)
                    user.save()
                    messages.success(request, 'Password set successfully! You can now log in.')
                    return redirect('login')
                else:
                    messages.error(request, 'Passwords do not match.')
                    return render(request, 'reset_password.html', {'uid': uid, 'token': token})
            return render(request, 'reset_password.html', {'uid': uid, 'token': token})
    
    print(f"DEBUG: Token validation failed - user: {user}, token passed check: {token_valid if user else False}")
    messages.error(request, 'The token is expired or invalid.')
    return render(request, 'password_reset_failed.html', {'error': 'The token is expired or invalid.'})



# Login View or Login Functionality 
@csrf_protect
def loginview(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Get user by email, then authenticate with username
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            user_obj = None
        
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
        else:
            user = None
        
        if user is not None:
            login(request, user)
            request.session["company_code"] = user.company_code_id
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            

            # Redirect based on role: SuperUser goes to admin dashboard, all others go to user dashboard
            if user.role == 'SuperUser':
                return redirect('superuser_dashboard')
            else:
                # All regular users (Uploader, Checker, Processor) go to user dashboard
                return redirect('user_dashboard')
        else:
            error_message = "Entered credentials are incorrect. Please enter correct credentials."
            return render(request, 'login.html', {'error': error_message})
         
    return render(request, 'login.html')



# logout View
@login_required
def logoutview(request):
    logout(request)
    return redirect('login')



# Password Reset Sent View
def password_reset_sent(request):
    return render(request, "password_reset_sent.html")



# Password Reset Done View
def password_reset_done(request):
    return render(request, "password_reset_done.html")



# SuperUser Dashboard View
@login_required
def superuser_dashboard(request):
    """
    SuperUser Dashboard handles:
    1. User Management (Create users)
    2. GST Details Management (Add/Edit GST registrations)
    """
    
    # Handle POST requests for both User Creation and GST Details
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # USER CREATION
        if action == 'create_user':
            user_form = UserManagementForm(request.POST)
            if user_form.is_valid():
                try:
                    user = user_form.save(commit=False, company=request.user.company_code)
                    user.save()
                    messages.success(request, f'User {user.username} created successfully!')
                    response = redirect('superuser_dashboard')
                    response['Location'] = response['Location'] + '?section=users'
                    return response
                except Exception as e:
                    messages.error(request, f'Failed to create user: {str(e)}')
            else:
                # Form validation errors
                for field, errors in user_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
        
        # GST DETAILS CREATION
        elif action == 'add_gst':
            gst_form = GSTDetailsForm(request.POST)
            if gst_form.is_valid():
                try:
                    gst_detail = gst_form.save(commit=False)
                    gst_detail.company = request.user.company_code
                    gst_detail.created_by = request.user
                    gst_detail.save()
                    messages.success(request, f'GST Details for {gst_detail.state} added successfully!')
                    response = redirect('superuser_dashboard')
                    response['Location'] = response['Location'] + '?section=settings'
                    return response
                except Exception as e:
                    messages.error(request, f'Failed to add GST details: {str(e)}')
            else:
                # Form validation errors
                for field, errors in gst_form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
    

    # Fetch all users from the same company
    users = User.objects.filter(company_code=request.user.company_code).order_by('-date_joined')
    

    # Fetch all GST details for the company
    gst_details = GSTDetails.objects.filter(company=request.user.company_code).order_by('state')
    

    # Create empty forms for the template
    user_form = UserManagementForm()
    gst_form = GSTDetailsForm()
    

    context = {
        'user_role': getattr(request.user, 'role', 'SuperUser'),
        'company': getattr(request.user, 'company_code', None),
        'users': users,
        'gst_details': gst_details,
        'user_form': user_form,
        'gst_form': gst_form,
    }

    return render(request, 'superuser_dashboard.html', context)


# User Dashboard View
@login_required
def user_dashboard(request):
    """
    User Dashboard with sections: Upload invoices , Pending Action (Standing status) , On Hold (Hold status) , Rejected (Rejected status),
    Approved (Approved status) , Accounted (Accounted status)
    
    Per-column prefix filters + pagination per section
    """
    
    # Current active section
    section = request.GET.get('section', 'upload')

    # Base queryset (company-level isolation)
    invoices_qs = Invoice.objects.filter(
        company=request.user.company_code
    ).order_by('-upload_date')

    
    #-------------------------------------------------------------------------------------------
    # Summary Counts for dashboard cards 
    # we are doing separate counts for each status to show on dashboard
    # invoices_qs is base queryset for all invoices of the company
    pending_count = invoices_qs.filter(status='Standing').count()
    hold_count = invoices_qs.filter(status='Hold').count()
    rejected_count = invoices_qs.filter(status='Rejected').count()
    approved_count = invoices_qs.filter(status='Approved').count()
    

    # we are not showing accounter count as of now on dashboard as per new BRD but keeping the code ready for future if we need to show it later
    # change 1 for accounted status 
    #accounted_count = invoices_qs.filter(status='Accounted').count()
    #-------------------------------------------------------------------------------------------



    # Get filter values
    vendor_prefix = request.GET.get('vendor_prefix', '')
    invoice_no_prefix = request.GET.get('invoice_no_prefix', '')

    #date_prefix = request.GET.get('date_prefix', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    amount_min = request.GET.get('amount_min', '')
    amount_max = request.GET.get('amount_max', '')
    status_prefix = request.GET.get('status_prefix', '')
    response_prefix = request.GET.get('response_prefix', '')
    file_prefix = request.GET.get('file_prefix', '')


    # Invoice Upload Limit Logic for USAGE METER CARD on dashboard - max 50 invoices per company as per BRD and show remaining usage
    
    MAX_INVOICES = 50

    user_invoice_count = Invoice.objects.filter(
        uploaded_by=request.user
    ).count()

    remaining_invoices = MAX_INVOICES - user_invoice_count
    usage_percentage = (user_invoice_count / MAX_INVOICES) * 100

    
    # Filtering logic
    def apply_filters(qs):

        if vendor_prefix:
            qs = qs.filter(vendor_name__istartswith=vendor_prefix)

        if invoice_no_prefix:
            qs = qs.filter(invoice_number__istartswith=invoice_no_prefix)

        #if date_prefix:
        #    qs = qs.filter(invoice_date__startswith=date_prefix)

        # Date filtering based on from_date and to_date
        if from_date:
            qs = qs.filter(invoice_date__gte=from_date)
        if to_date:
            qs = qs.filter(invoice_date__lte=to_date)

        if status_prefix:
            qs = qs.filter(status__istartswith=status_prefix)

        if response_prefix:
            qs = qs.filter(response__istartswith=response_prefix)

        if file_prefix:
            qs = qs.filter(file_name__istartswith=file_prefix)

        try:
            if amount_min:
                qs = qs.filter(invoice_value__gte=Decimal(amount_min))
            if amount_max:
                qs = qs.filter(invoice_value__lte=Decimal(amount_max))
        except InvalidOperation:
            pass

        return qs


    # 🔽 Helper: Pagination
    def paginate(qs, page_param):
        paginator = Paginator(qs, 10)
        page_number = request.GET.get(page_param, 1)

        try:
            return paginator.page(page_number)
        except PageNotAnInteger:
            return paginator.page(1)
        except EmptyPage:
            return paginator.page(paginator.num_pages)
        

    # 🔽 Section-wise data
    pending_invoices = paginate(
        apply_filters(invoices_qs.filter(status='Standing')),
        'pending_page'
    )

    hold_invoices = paginate(
        apply_filters(invoices_qs.filter(status='Hold')),
        'hold_page'
    )

    rejected_invoices = paginate(
        apply_filters(invoices_qs.filter(status='Rejected')),
        'rejected_page'
    )

    approved_invoices = paginate(
        apply_filters(invoices_qs.filter(status='Approved')),
        'approved_page'
    )

    
    # change 2 for accounted status
    '''
    accounted_invoices = paginate(
        apply_filters(invoices_qs.filter(status='Accounted')),
        'accounted_page'
    )
    '''

    context = {
        'section': section,

        # Summary counts for dashboard cards 
        'pending_count': pending_count,
        'hold_count': hold_count,
        'rejected_count': rejected_count,
        'approved_count': approved_count,
        #'accounted_count': accounted_count,


        # Paginated invoice lists for each status
        'pending_invoices': pending_invoices,
        'hold_invoices': hold_invoices,
        'rejected_invoices': rejected_invoices,
        'approved_invoices': approved_invoices,
        #'accounted_invoices': accounted_invoices,


        'filters': {
            'vendor_prefix': vendor_prefix,
            'invoice_no_prefix': invoice_no_prefix,

            #'date_prefix': date_prefix,
            'from_date': from_date,
            'to_date': to_date,

            'amount_min': amount_min,
            'amount_max': amount_max,
            'status_prefix': status_prefix,
            'response_prefix': response_prefix,
            'file_prefix': file_prefix,
        },
 
        # Data for Usage Meter Card on Dashboard
        "user_invoice_count": user_invoice_count,
        "remaining_invoices": remaining_invoices,
        "usage_percentage": usage_percentage,
        "max_invoices": MAX_INVOICES,

    }

    return render(request, 'user_dashboard.html', context)



# Upload Invoice View
# this view is handling the file upload and also mapping the extracted data to invoice model using the map_api_data_to_invoice function 

@login_required
@csrf_protect
def upload_invoice(request):

    """
    Handle invoice file upload - PDF, Word, JPEG, max 5MB
    """

    if request.method == 'POST':
        files = request.FILES.getlist('invoice_files')
        
        if not files:
            messages.error(request, 'No files selected.')
            return redirect('user_dashboard')
        
        # Allowed extensions per BRD
        allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg']
        max_size = 5 * 1024 * 1024  # 5MB
        
        uploaded_count = 0
        
        for file in files:
            # Check file extension
            file_ext = os.path.splitext(file.name)[1].lower()
            if file_ext not in allowed_extensions:
                messages.error(request, f'{file.name}: Invalid format. Only PDF, Word, JPEG allowed.')
                continue
            
            
            # Check file size
            if file.size > max_size:
                messages.error(request, f'{file.name}: File exceeds 5MB limit.')
                continue
            

            # Save file
            #fs = FileSystemStorage(location=settings.MEDIA_ROOT / 'invoices')
            fs= FileSystemStorage()
            filename = fs.save(f"invoices/{file.name}", file)
            file_path = fs.url(filename)
            

            # Create Invoice record with status=Standing
            invoice = Invoice.objects.create(
                company=request.user.company_code,
                uploaded_by=request.user,
                vendor_name='Pending',  # To be extracted/manually entered later
                invoice_number='Pending',
                invoice_date=timezone.now().date(),
                invoice_value=0.00,
                file_name=file.name,

                #file_path=str(settings.MEDIA_ROOT / 'invoices' / filename),
                file_path=file_path,

                status='Standing',
                response='Upload successful, awaiting processing'
            )

            uploaded_count += 1
            
            # Extract data using stimulated API response
            #map_api_data_to_invoice(invoice, api_response_test)  
            
            #---------------------------------------------------------------------------
            # Real OCR API call with file path and mapping to invoice model
            #Replace This Line:
            #from validations.invoice_mapper import call_ocr_api

            # Get absolute file path (IMPORTANT)
            absolute_path = fs.path(filename)

            # Call real OCR API
            ocr_response = call_ocr_api(absolute_path)
            

            if ocr_response:
                map_api_data_to_invoice(invoice,ocr_response)
                # Keep in Pending Action bucket
                invoice.status = "Standing"
                invoice.response = "OCR and validation completed"
                invoice.save()
            else:
                # Keep visible in Pending Action even on OCR failure
                invoice.status = "Standing"
                invoice.response = "OCR API failed (pending manual review)"
                invoice.save()
         
        if uploaded_count > 0:
            messages.success(request, f'{uploaded_count} invoice(s) uploaded successfully.')
        
        return redirect('user_dashboard')
    
    return redirect('user_dashboard')



# 3rd version implementing Invoice button data mapping using session data and popup MODAL
@login_required
@csrf_protect
def update_invoice_status(request, invoice_id):

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status not in ['Approved', 'Rejected', 'Hold']:     # change 3 for accounted status # removed 'Accounted' from list here
            messages.error(request, 'Invalid status.')
            return redirect('user_dashboard')

        try:
            invoice = Invoice.objects.get(
                id=invoice_id,
                company=request.user.company_code
            )

            # STORE RAW DATA ONLY ON APPROVE
            if new_status == 'Approved':
                request.session[f"invoice_raw_data_{invoice.id}"] = api_response_test  # store raw data in session for modal popup

            invoice.status = new_status
            invoice.response = f'Status updated to {new_status} by {request.user.username}'
            invoice.save()

            messages.success(
                request,
                f'Invoice {invoice.invoice_number} marked as {new_status}.'
            )

        except Invoice.DoesNotExist:
            messages.error(request, 'Invoice not found.')

    return redirect('user_dashboard')


# -----======================== MODAL POPUP INVOICE BUTTON FUNCTIONALITY ========================-----
# In this view we will get the raw data from session and return as JsonResponse
# Get Invoice Raw Data View for Modal Popup
# On Pending Action tab then Invoice Status then when Invoice button 
# is clicked this view will be called to get the raw data from session 
'''
@login_required
def get_invoice_raw_data(request, invoice_id):

    """
    Returns invoice data for the modal popup.
    Currently using data from data_gathering.py
    """
    # Use the full JSON from data_gathering.py
    # data = api_response_test
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        company=request.user.company_code,
    )

    # USE DATABASE STORED OCR JSON
    data = invoice.raw_ocr_response or {}


    
    # ==================================== Invoice Calculation 1 Data Extraction ==================================== #
    # Have done backend calculation for Table Check (Invoice Calculation 1) to show in modal popup for better accuracy and to reduce frontend       

    table_check = data.get("result", {}).get("CHECKS", {}).get("table_data", {}).get("Table_Check_data", "[]")

    # Table_Check_data is a JSON string; convert to Python list
    import json
    try:
        table_check_list = json.loads(table_check)
    except:
        table_check_list = []

    TABLE_LINE_TOLERANCE = Decimal("1")

    def to_decimal(val):
        if val is None:
            return None
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("%", "").strip()
            if not cleaned:
                return None
            try:
                return Decimal(cleaned)
            except Exception:
                return None
        return None

    def compute_line_fields(item):
        qty = to_decimal(item.get("item_quantity"))
        unit = to_decimal(item.get("unit_price"))
        amount = to_decimal(item.get("amount"))

        # 1. take tax_rate to calculate qty + tax and qty + 2 * tax
        tax_rate = to_decimal(item.get("tax_rate"))

        calc = None
        if qty is not None and unit is not None:
            calc = (qty * unit).quantize(Decimal("0.01"))
            item["qty_unitprice"] = float(calc)

        if calc is not None and amount is not None:
            diff = abs(calc - amount)
            item["check1"] = "Matched" if diff <= TABLE_LINE_TOLERANCE else "Not Matched"
        else:
            item["check1"] = "-"

        # 2. TAX Calculations 
        if calc is not None and tax_rate is not None:
            tax_amount = (calc * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

            item["qty_unit+rate_qty_unit"] = float(calc + tax_amount)
            item["qty_unit+2_rate_qty_unit"] = float(calc + (tax_amount * 2))

        else:
            item["qty_unit+rate_qty_unit"] = "-"
            item["qty_unit+2_rate_qty_unit"] = "-"  


        #return calc, amount
        return item 

    for item in table_check_list:
        compute_line_fields(item)

    if table_check_list:                                                           # line items calculations 
        ic1_basic = table_check_list[0]  # take first line item
        ocr_amount_dec = to_decimal(ic1_basic.get("amount"))
        table_sum_dec = to_decimal(ic1_basic.get("qty_unitprice"))

        if ocr_amount_dec is not None and table_sum_dec is not None:
            diff = abs(ocr_amount_dec - table_sum_dec)
            status = "Matched" if diff <= TABLE_LINE_TOLERANCE else "Not Matched"
            ocr_amount_val = float(ocr_amount_dec)
            table_sum_val = float(table_sum_dec)
        else:
            status = "-"
            ocr_amount_val = "-"
            table_sum_val = "-"
        
        ic1_data = {
            "basic_amount": {
                "ocr_amount": ocr_amount_val,
                "table_sum": table_sum_val,
                "status": status
            }
        }

    else:
        ic1_data = {
            "basic_amount": {
                "ocr_amount": "-",
                "table_sum": "-",
                "status": "-"
            }
        }

    # ==================================== Account Check Data Extraction ==================================== #
    # ✅ Extract Account_check ONCE and reuse for all buttons
    account_check = data.get("result", {}).get("CHECKS", {}).get("Account_check", {})
    invoice_meta = data.get("result", {}).get("Invoice_data", {})
    
    # Helper function to extract parameter data
    def extract_account_param(key):
        param = account_check.get(key, {})
        return {
            "gst_portal": param.get("Gst_Portal", ""),
            "invoice_data": param.get("Invoice_data", ""),
            "status": param.get("status", "")
        }
    
    # ===== 1. COMPLETE ACCOUNT CHECK (for Account Button) ===== #
    account_check_full = {
        "Complete_Invoice": extract_account_param("Complete_Invoice"),
        "Customer_Adress": extract_account_param("Customer_Adress"),
        "Customer_Name": extract_account_param("Customer_Name"),
        "Invoice_Blocked_Credit": extract_account_param("Invoice_Blocked_Credit"),
        "Invoice_Date": extract_account_param("Invoice_Date"),
        "Invoice_Number": extract_account_param("Invoice_Number"),
        "Invoice_RCM-Services": extract_account_param("Invoice_RCM-Services"),
        "Pre_year": extract_account_param("Pre_year"),
        "gstnumber_gstcharged": extract_account_param("gstnumber_gstcharged"),
        "valid_invoice": extract_account_param("valid_invoice")
    }
    
    # ===== 2. PARTIAL DATA (for Invoice Button - Name & Address) ===== #
    customer_name = account_check.get("Customer_Name", {})
    customer_address = account_check.get("Customer_Adress", {})
    
    # Address matching logic for status 
    gst_address_text = customer_address.get("Gst_Portal", "")
    invoice_address_text = customer_address.get("Invoice_data", "")

    match_percent = address_match_percentage(gst_address_text, invoice_address_text)
    address_status = "Matched" if match_percent >= 60 else "Not Matched"

    account_check_data = {
        "customer_name": {
            "gst_portal": customer_name.get("Gst_Portal", "-"),
            "invoice_data": customer_name.get("Invoice_data", "-"),
            "status": customer_name.get("status", "-")
        },
        "customer_address": {
            "gst_portal": gst_address_text or "-",
            "invoice_data": invoice_address_text or "-",
            "status": address_status,
            "match_percentage": round(match_percent, 2)
        }
    }


    # ===== 3. OTHER PARAMETER CHECK (for Invoice Button) ===== #
    # Reuse extract_account_param helper for other parameters
    other_parameter_check = {
        "invoice_date": extract_account_param("Invoice_Date"),
        "invoice_number": extract_account_param("Invoice_Number"),
        "previous_year": extract_account_param("Pre_year"),
        "gst_mentioned": extract_account_param("gstnumber_gstcharged"),
        "valid_invoice": extract_account_param("valid_invoice")
    }

    # Fill missing data dynamically from available invoice/account data (maintain consistency with "-")
    gst_data = other_parameter_check.get("gst_mentioned", {})
    if not gst_data.get("invoice_data") or gst_data.get("invoice_data") == "":
        gst_data["invoice_data"] = (
            account_check.get("Vendor_Gst_mentioned", {}).get("Invoice_data")
            or invoice_meta.get("Vendor Gst No.")
            or ""
        )

    valid_data = other_parameter_check.get("valid_invoice", {})
    invoice_type = (
        invoice_meta.get("Tax_Invoice")
        or invoice_meta.get("InvoiceType")
        or invoice_meta.get("Invoice_Type")
        or ""
    )
    if not valid_data.get("invoice_data") or valid_data.get("invoice_data") == "":
        valid_data["invoice_data"] = invoice_type
    if not valid_data.get("status") or valid_data.get("status") == "":
        allowed_types = {"PI", "Estimate", "Commercial", "Supply invoice", "Challan"}
        valid_data["status"] = "YES" if invoice_type in allowed_types else "NO"

    # ==================================== Invoice Calculation 2 Data Extraction ==================================== #
    
    INVOICE_CALCULATION_2_TOLERANCE = 1

    # Reuse table sum from Invoice Calculation 1
    table_sum = ic1_basic.get("qty_unitprice") if table_check_list else None

    # OCR invoice-level data
    invoice_data = invoice_meta

    # Extract OCR Total Tax and OCR Invoice Total
    ocr_tax = invoice_data.get("TotalTax")
    ocr_total = invoice_data.get("InvoiceTotal") 

    # Safe numeric conversion
    def to_float(val):
        try:
            return float(val)
        except:
            return None
        
    table_sum_f = to_float(table_sum)
    ocr_tax_f = to_float(ocr_tax)
    ocr_total_f = to_float(ocr_total)

    # Perform calculation and Comparison
    if table_sum_f is not None and ocr_tax_f is not None and ocr_total_f is not None:
        expected_total = table_sum_f + ocr_tax_f
        diff = abs(expected_total - ocr_total_f)

        ic2_status = "Matched" if diff <= INVOICE_CALCULATION_2_TOLERANCE else "Not Matched"
    else:
        expected_total = "-"
        ic2_status = "-"
    
    invoice_calculation_2 = {
        "total_amount": {
            "table_sum": table_sum_f if table_sum_f is not None else "-",
            "ocr_tax": ocr_tax_f if ocr_tax_f is not None else "-",
            "ocr_total": ocr_total_f if ocr_total_f is not None else "-",
            "status": ic2_status
        }
    }


    # ============================= PAN CHECK =========================== #
    tax_check_raw = data.get("result", {}).get("CHECKS", {}).get("tax_check", {})

    pan_check_data = {
        "vendor_206ab": tax_check_raw.get("Vendor_206AB", {}).get("status", "-"),
        "vendor_pan_active": tax_check_raw.get("Vendor_Pan_Active", {}).get("status", "-"),
        "vendor_pan_aadhar_linked": tax_check_raw.get("Vendor_Pan-Adhar_Linked", {}).get("status", "-"),
    }


    # ============================= Tax Check =========================== #
    # Reuse already-extracted account_check
    # Get tax items from Invoice_data
    tax_items = invoice_meta.get("Tax Items", {}) or {}

    def safe_amount(tax_key):
        tax_obj = tax_items.get(tax_key, {}) or {}
        return to_float(tax_obj.get("amount")) or 0
    
    igst_amount = safe_amount("IGST")
    cgst_amount = safe_amount("CGST")
    sgst_amount = safe_amount("SGST")
    
    # Determine tax type based on what's present
    if igst_amount > 0:
        tax_type = "IGST"
    elif cgst_amount > 0 or sgst_amount > 0:
        tax_type = "CGST + SGST"
    else:
        tax_type = "-"

    # Calculate total tax rate (approximate based on total tax / subtotal)
    try:
        subtotal = to_float(invoice_meta.get("SubTotal")) or 0
        total_tax = to_float(invoice_meta.get("TotalTax")) or 0
        tax_rate_percent = round((total_tax / subtotal) * 100, 2) if subtotal > 0 else 0
        tax_rate = f"{tax_rate_percent}%"
    except:
        tax_rate = "-"

    tax_check_data = {
        "tax_rate": tax_rate,
        "tax_type": tax_type,
        "input_credit": account_check.get("Invoice_Blocked_Credit", {}).get("status", "-"),
        "rcm_fc": account_check.get("Invoice_RCM-Services", {}).get("status", "-"),
    }


    # Combine everything to send to frontend
    response_data = {
        "invoice_calculation_1": ic1_data["basic_amount"],
        "invoice_calculation_2": invoice_calculation_2["total_amount"],
        "account_check": account_check_data,          # Partial (Name & Address) for Invoice button
        "account_check_full": account_check_full,     # ✅ Complete (10 fields) for Account button
        "tax_check": tax_check_data,
        "pan_check": pan_check_data,
        "other_parameter_check": other_parameter_check,  
        "table_check": table_check_list,  
        "result": data.get("result", {})
    } 


    return JsonResponse(response_data, safe=False)
'''

# 2nd version of get_invoice_raw_data view
@login_required
def get_invoice_raw_data(request, invoice_id):

    """
    Returns invoice data for the modal popup.
    Currently using data from data_gathering.py
    """
 
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        company=request.user.company_code,
    )

    data = invoice.raw_ocr_response or {}
    
    # ==================================== Invoice Calculation 1 Data Extraction ==================================== #

    table_check = data.get("result", {}).get("CHECKS", {}).get("table_data", {}).get("Table_Check_data", "[]")

    import json
    try:
        table_check_list = json.loads(table_check)
    except:
        table_check_list = []

    TABLE_LINE_TOLERANCE = Decimal("1")

    def to_decimal(val):
        if val is None:
            return None
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, float)):
            return Decimal(str(val))
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("%", "").replace("₹", "").strip()
            if not cleaned:
                return None
            try:
                return Decimal(cleaned)
            except:
                return None
        return None


    def compute_line_fields(item):
        qty = to_decimal(item.get("item_quantity"))
        unit = to_decimal(item.get("unit_price"))
        amount = to_decimal(item.get("amount"))
        tax_rate = to_decimal(item.get("tax_rate"))

        calc = None

        # ---------------- Basic Calculation ---------------- #
        if qty is not None and unit is not None:
            calc = (qty * unit).quantize(Decimal("0.01"))
            item["qty_unitprice"] = float(calc)
        else:
            item["qty_unitprice"] = "-"

        # ---------------- Smart Matching Logic ---------------- #
        if calc is not None and amount is not None:

            matched = False

            # Case 1: Amount = Basic only
            if abs(calc - amount) <= TABLE_LINE_TOLERANCE:
                matched = True

            # If tax exists, check tax scenarios
            if tax_rate is not None:

                tax_amount = (calc * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

                # Case 2: Amount = Basic + 1 Tax (IGST)
                if abs((calc + tax_amount) - amount) <= TABLE_LINE_TOLERANCE:
                    matched = True

                # Case 3: Amount = Basic + 2 Tax (CGST + SGST)
                if tax_rate <= Decimal("14"):   # prevents false 2x for 18% IGST
                    if abs((calc + (tax_amount * 2)) - amount) <= TABLE_LINE_TOLERANCE:
                        matched = True

            item["check1"] = "Matched" if matched else "Not Matched"

        else:
            item["check1"] = "-"

        # ---------------- Extra Tax Display Columns ---------------- #
        if calc is not None and tax_rate is not None:
            tax_amount = (calc * tax_rate / Decimal("100")).quantize(Decimal("0.01"))

            item["qty_unit+rate_qty_unit"] = float(calc + tax_amount)
            item["qty_unit+2_rate_qty_unit"] = float(calc + (tax_amount * 2))
        else:
            item["qty_unit+rate_qty_unit"] = "-"
            item["qty_unit+2_rate_qty_unit"] = "-"

        return item


    # Apply calculation to each row
    for item in table_check_list:
        compute_line_fields(item)


    # ---------------- Invoice Level Basic Amount Comparison ---------------- #

    table_sum_dec = Decimal("0")

    for item in table_check_list:
        line_total = to_decimal(item.get("qty_unitprice"))
        if line_total is not None:
            table_sum_dec += line_total

    invoice_meta = data.get("result", {}).get("Invoice_data", {})

    ocr_amount_dec = to_decimal(invoice_meta.get("SubTotal"))

    if table_check_list and ocr_amount_dec is not None:
        diff = abs(ocr_amount_dec - table_sum_dec)
        status = "Matched" if diff <= TABLE_LINE_TOLERANCE else "Not Matched"
        ocr_amount_val = float(ocr_amount_dec)
        table_sum_val = float(table_sum_dec)
    else:
        status = "-"
        ocr_amount_val = "-"
        table_sum_val = "-"

    ic1_data = {
        "basic_amount": {
            "ocr_amount": ocr_amount_val,
            "table_sum": table_sum_val,
            "status": status
        }
    }

    # ==================================== Account Check Data Extraction ==================================== #

    account_check = data.get("result", {}).get("CHECKS", {}).get("Account_check", {})

    def extract_account_param(key):
        param = account_check.get(key, {})
        return {
            "gst_portal": param.get("Gst_Portal", ""),
            "invoice_data": param.get("Invoice_data", ""),
            "status": param.get("status", "")
        }

    account_check_full = {
        "Complete_Invoice": extract_account_param("Complete_Invoice"),
        "Customer_Adress": extract_account_param("Customer_Adress"),
        "Customer_Name": extract_account_param("Customer_Name"),
        "Invoice_Blocked_Credit": extract_account_param("Invoice_Blocked_Credit"),
        "Invoice_Date": extract_account_param("Invoice_Date"),
        "Invoice_Number": extract_account_param("Invoice_Number"),
        "Invoice_RCM-Services": extract_account_param("Invoice_RCM-Services"),
        "Pre_year": extract_account_param("Pre_year"),
        "gstnumber_gstcharged": extract_account_param("gstnumber_gstcharged"),
        "valid_invoice": extract_account_param("valid_invoice")
    }

    customer_name = account_check.get("Customer_Name", {})
    customer_address = account_check.get("Customer_Adress", {})

    gst_address_text = customer_address.get("Gst_Portal", "")
    invoice_address_text = customer_address.get("Invoice_data", "")

    match_percent = address_match_percentage(gst_address_text, invoice_address_text)
    address_status = "Matched" if match_percent >= 60 else "Not Matched"

    account_check_data = {
        "customer_name": {
            "gst_portal": customer_name.get("Gst_Portal", "-"),
            "invoice_data": customer_name.get("Invoice_data", "-"),
            "status": customer_name.get("status", "-")
        },
        "customer_address": {
            "gst_portal": gst_address_text or "-",
            "invoice_data": invoice_address_text or "-",
            "status": address_status,
            "match_percentage": round(match_percent, 2)
        }
    }

    other_parameter_check = {
        "invoice_date": extract_account_param("Invoice_Date"),
        "invoice_number": extract_account_param("Invoice_Number"),
        "previous_year": extract_account_param("Pre_year"),
        "gst_mentioned": extract_account_param("gstnumber_gstcharged"),
        "valid_invoice": extract_account_param("valid_invoice")
    }

    # ==================================== Invoice Calculation 2 Data Extraction ==================================== #

    INVOICE_CALCULATION_2_TOLERANCE = 1

    table_sum_f = float(table_sum_val) if table_sum_val != "-" else None

    ocr_tax = invoice_meta.get("TotalTax")
    ocr_total = invoice_meta.get("InvoiceTotal")

    def to_float(val):
        try:
            return float(val)
        except:
            return None

    ocr_tax_f = to_float(ocr_tax)
    ocr_total_f = to_float(ocr_total)

    if table_sum_f is not None and ocr_tax_f is not None and ocr_total_f is not None:
        expected_total = table_sum_f + ocr_tax_f
        diff = abs(expected_total - ocr_total_f)
        ic2_status = "Matched" if diff <= INVOICE_CALCULATION_2_TOLERANCE else "Not Matched"
    else:
        expected_total = "-"
        ic2_status = "-"

    invoice_calculation_2 = {
        "total_amount": {
            "table_sum": table_sum_f if table_sum_f is not None else "-",
            "ocr_tax": ocr_tax_f if ocr_tax_f is not None else "-",
            "ocr_total": ocr_total_f if ocr_total_f is not None else "-",
            "status": ic2_status
        }
    }

    # ============================= PAN CHECK =========================== #

    tax_check_raw = data.get("result", {}).get("CHECKS", {}).get("tax_check", {})

    pan_check_data = {
        "vendor_206ab": tax_check_raw.get("Vendor_206AB", {}).get("status", "-"),
        "vendor_pan_active": tax_check_raw.get("Vendor_Pan_Active", {}).get("status", "-"),
        "vendor_pan_aadhar_linked": tax_check_raw.get("Vendor_Pan-Adhar_Linked", {}).get("status", "-"),
    }

    # ============================= Tax Check =========================== #

    tax_items = invoice_meta.get("Tax Items", {}) or {}

    def safe_amount(tax_key):
        tax_obj = tax_items.get(tax_key, {}) or {}
        return to_float(tax_obj.get("amount")) or 0

    igst_amount = safe_amount("IGST")
    cgst_amount = safe_amount("CGST")
    sgst_amount = safe_amount("SGST")

    if igst_amount > 0:
        tax_type = "IGST"
    elif cgst_amount > 0 or sgst_amount > 0:
        tax_type = "CGST + SGST"
    else:
        tax_type = "-"

    try:
        subtotal = to_float(invoice_meta.get("SubTotal")) or 0
        total_tax = to_float(invoice_meta.get("TotalTax")) or 0
        tax_rate_percent = round((total_tax / subtotal) * 100, 2) if subtotal > 0 else 0
        tax_rate = f"{tax_rate_percent}%"
    except:
        tax_rate = "-"

    tax_check_data = {
        "tax_rate": tax_rate,
        "tax_type": tax_type,
        "input_credit": account_check.get("Invoice_Blocked_Credit", {}).get("status", "-"),
        "rcm_fc": account_check.get("Invoice_RCM-Services", {}).get("status", "-"),
    }

    response_data = {
        "invoice_calculation_1": ic1_data["basic_amount"],
        "invoice_calculation_2": invoice_calculation_2["total_amount"],
        "account_check": account_check_data,
        "account_check_full": account_check_full,
        "tax_check": tax_check_data,
        "pan_check": pan_check_data,
        "other_parameter_check": other_parameter_check,
        "table_check": table_check_list,
        "result": data.get("result", {})
    }

    return JsonResponse(response_data, safe=False)



# Download Validation Summary View
# This view generates and serves an Excel file summarizing the validation checks for a given invoice
# 2nd version with dynamic summary data population and improved formatting 
@login_required
def download_validation_summary(request, invoice_id):
    
    # Download validation summary for an invoice in Excel format
    try:
        invoice = Invoice.objects.get(
            id=invoice_id,
            company=request.user.company_code
        )

    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('user_dashboard')


    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Validation Summary"


    # Header styling
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)


    # Title
    ws['A1'] = 'Invoice Validation Summary'
    ws['A1'].font = Font(bold=True, size=16)
    ws.merge_cells('A1:D1')


    # Invoice Details Section
    ws['A3'] = 'Invoice Details'
    ws['A3'].font = Font(bold=True, size=14)

    details = [
        ['Vendor Name', invoice.vendor_name],
        ['Invoice Number', invoice.invoice_number],
        ['Invoice Date', invoice.invoice_date.strftime('%d %b %Y')],
        ['Invoice Value', f'₹{invoice.invoice_value}'],
        ['Status', invoice.status],
        ['Upload Date', invoice.upload_date.strftime('%d %b %Y %H:%M')],
        ['Uploaded By', invoice.uploaded_by.username if invoice.uploaded_by else 'N/A'],
        ['File Name', invoice.file_name],
        ['Response', invoice.response or 'N/A'],
    ]

    row = 4
    for label, value in details:
        ws[f'A{row}'] = label
        ws[f'A{row}'].font = Font(bold=True)
        ws[f'B{row}'] = value
        row += 1

   
    # Validation Checks Section       
    row += 2
    ws[f'A{row}'] = 'Validation Checks'
    ws[f'A{row}'].font = Font(bold=True, size=14)

    row += 1

    check_headers = ['Check Type', 'Status', 'Details', 'Result']
    for col_idx, header in enumerate(check_headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')



    # Fetch Validation Summary
 

    import json
    summary = invoice.validation_summary

    # If stored as string , convert to dict
    if isinstance(summary, str):
        try: 
            summary = json.loads(summary)
        except:
            summary = {}

    if not summary:
        summary = {"categories": []}
    
    row += 1

    
    # 2nd version with dynamic summary data population and improved formatting 
    # Populate Validation Rows

    summary = invoice.validation_summary
    
    # If stored as string, convert to dict
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except:
            summary = {}
    
    if not summary:
        summary = {"categories": []}
    
    row += 1
    
    # Iterate through categories and checks
    for category_data in summary.get("categories", []):
        category_name = category_data.get("category", "")
        checks = category_data.get("checks", [])
        
        for check in checks:
            check_type = check.get("check_name", "")
            status = check.get("status", "")
            details = check.get("details", "")
            
            # Determine result based on status
            if status == "Pass":
                result = "Valid"
                status_color = "008000"  # Green
            elif status == "Fail":
                result = "Invalid"
                status_color = "FF0000"  # Red
            else:
                result = "Pending"
                status_color = "FFA500"  # Orange
            
            # Column 1 - Check Type
            ws.cell(row=row, column=1, value=check_type)
            
            # Column 2 - Status
            status_cell = ws.cell(row=row, column=2, value=status)
            status_cell.font = Font(color=status_color, bold=True)
            
            # Column 3 - Details
            ws.cell(row=row, column=3, value=details)
            
            # Column 4 - Result
            result_cell = ws.cell(row=row, column=4, value=result)
            result_cell.font = Font(color=status_color, bold=True)
            
            row += 1


    # Column Widths
    ws.column_dimensions['A'].width = 25
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 45
    ws.column_dimensions['D'].width = 15

    # Prepare Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="Invoice_{invoice.invoice_number}_Validation_Summary.xlsx"'
    )

    wb.save(response)
    return response


#---------------------------------------------------------------------------------------------------
# Edits an existing GST registration record for the logged-in user's company.
# - Ensures only authenticated users can access this view.
# - Restricts editing to GST records belonging to the user's company.
# - Processes form submission via POST request.
# - Displays success or validation error messages accordingly.
# - Redirects back to the dashboard Settings section after processing.
@login_required
def edit_gst_detail(request, gst_id):
    """
    Edit existing GST registration detail.
    Only allows editing GST details belonging to the user's company.
    """
    gst_detail = get_object_or_404(GSTDetails, id=gst_id, company=request.user.company_code)
    
    if request.method == 'POST':
        form = GSTDetailsForm(request.POST, instance=gst_detail)
        if form.is_valid():
            form.save()
            messages.success(request, f'GST Details for {gst_detail.state} updated successfully!')
            response = redirect('superuser_dashboard')
            response['Location'] = response['Location'] + '?section=settings'
            return response
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    response = redirect('superuser_dashboard')
    response['Location'] = response['Location'] + '?section=settings'
    return response
#--------------------------------------------------------------------------------------------------


#-------------------------------------------------------------------------------------------------
# This View Handles Deletion of GST Details
# Deletes a GST registration record for the logged-in user's company.
# - Ensures only authenticated users can access this view.
# - Restricts deletion to GST records belonging to the user's company.
# - Allows deletion only via POST request for safety.
# - After deletion, redirects back to the dashboard Settings section
#   with a success message.
@login_required
def delete_gst_detail(request, gst_id):
    """
    Delete GST registration detail.
    Only allows deleting GST details belonging to the user's company.
    """
    gst_detail = get_object_or_404(GSTDetails, id=gst_id, company=request.user.company_code)
    
    if request.method == 'POST':
        state_name = gst_detail.state
        gst_detail.delete()
        messages.success(request, f'GST Details for {state_name} deleted successfully!')
    
    response = redirect('superuser_dashboard')
    response['Location'] = response['Location'] + '?section=settings'
    return response
#-------------------------------------------------------------------------------------------------

