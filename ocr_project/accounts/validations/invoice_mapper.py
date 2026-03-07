import re
from datetime import datetime
from accounts.validations.data_gathering import extract_invoice_core_fields
import requests

# 🔗 External OCR API endpoint
OCR_URL = "https://ngtechocr.azurewebsites.net/process-invoice-withchecks-updated-splitting"


# Calls the external OCR API to process an invoice PDF.
# Parameters: file_path (str): Absolute path of the uploaded invoice PDF.
# Returns: dict - Parsed JSON response from OCR API if successful. none - If API fails or exception occurs

def call_ocr_api(file_path):

    # Open the uploaded PDF file in binary mode 
    try:
        with open(file_path, "rb") as f:

            # Prepare file payload for multipart/form-data request
            files = {"pdf_file": f}

            # Authentication and required API parameters 
            data = {
                "user_id": "BC_User1",
                "password": "1234@India",
                "App": "WFS",
                "pan": ""
            }
            
            # Send POST request to OCR API
            # - files: sends PDF
            # - data: sends credentials and metadata
            # - timeout: prevent hanging requests
            response = requests.post(OCR_URL, files=files, data=data, timeout=60)

        # If API call successful
        if response.status_code == 200:
            return response.json()
        
        # If API returned error status
        else:
            print("OCR Error:", response.text)
            return None

    # Catch unexpected errors (network issues, file issues, etc.)    
    except Exception as e:
        print("OCR Exception:", str(e))
        return None
    

# Dynamic Validation Rules Configuration
VALIDATION_RULES = [
    # Invoice basics
    {"category": "Invoice", "field": "VendorName", "check_name": "Vendor Name Present", "type": "required"},
    {"category": "Invoice", "field": "InvoiceId", "check_name": "Invoice Number Present", "type": "required"},    
    {"category": "Invoice", "field": "InvoiceDate", "check_name": "Invoice Date Present", "type": "required"},
    {"category": "Invoice", "field": "InvoiceDate", "check_name": "Invoice Date Format (YYYY-MM-DD)", "type": "date_iso"},
    {"category": "Invoice", "field": "InvoiceTotal", "check_name": "Invoice Value Present", "type": "required"},
    {"category": "Invoice", "field": "InvoiceTotal", "check_name": "Invoice Value Positive", "type": "positive_number"},


    # Tax consistency basics (these fields exist in Invoice_data)
    {"category": "Tax", "field": "SubTotal", "check_name": "SubTotal Present", "type": "required"},
    {"category": "Tax", "field": "SubTotal", "check_name": "SubTotal Positive", "type": "positive_number"},
    {"category": "Tax", "field": "TotalTax", "check_name": "Total Tax Present", "type": "required"},
    {"category": "Tax", "field": "TotalTax", "check_name": "Total Tax Non-Negative", "type": "non_negative_number"},
    {"category": "Tax", "field": "Currency", "check_name": "Currency Present", "type": "required"},
    {"category": "Tax", "field": "Currency", "check_name": "Currency is INR", "type": "one_of", "options": ["INR"]},

    # Compliance/document checks (these fields exist in Invoice_data)
    {"category": "Compliance", "field": "Vendor Gst No.", "check_name": "Vendor GST Number Present", "type": "required"},
    {"category": "Compliance", "field": "Vendor Gst No.", "check_name": "Vendor GST Format Valid", "type": "gstin_format"},
    {"category": "Compliance", "field": "Tax_Invoice", "check_name": "Tax Invoice Type Present", "type": "required"},
    {"category": "Compliance", "field": "Cutomer Gst No.", "check_name": "Customer GST Number Present", "type": "required"},
    {"category": "Compliance", "field": "Cutomer Gst No.", "check_name": "Customer GST Format Valid", "type": "gstin_format"},

]


# Safely converts a given value to float.
def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

#  Validates whether the provided value is a valid Indian GSTIN.
def _is_valid_gstin(value):
    if not value:
        return False
    gstin = str(value).strip().upper()
    return bool(re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\dZ[A-Z0-9]$", gstin))


def _evaluate_rule(invoice_data, rule):
    field_name = rule["field"]
    field_value = invoice_data.get(field_name)
    rule_type = rule.get("type", "required")

    if rule_type == "required":
        return bool(field_value)

    if rule_type == "positive_number":
        num = _to_float(field_value)
        return num is not None and num > 0

    if rule_type == "non_negative_number":
        num = _to_float(field_value)
        return num is not None and num >= 0

    if rule_type == "date_iso":
        if not field_value:
            return False
        try:
            datetime.strptime(str(field_value), "%Y-%m-%d")
            return True
        except ValueError:
            return False
        
    if rule_type == "one_of":
        allowed = [str(v).strip().lower() for v in rule.get("options", [])]
        return str(field_value).strip().lower() in allowed if field_value is not None else False

    if rule_type == "gstin_format":
        return _is_valid_gstin(field_value)

    return bool(field_value)


def run_dynamic_validations(invoice_data):
    categories = {}

    for rule in VALIDATION_RULES:
        category = rule["category"]
        is_valid = _evaluate_rule(invoice_data, rule)

        check_result = {
            "check_name": rule["check_name"],
            "status": "Pass" if is_valid else "Fail",
            "details": f"{rule['check_name']} {'passed' if is_valid else 'failed'}"
        }

        if category not in categories:
            categories[category] = []

        categories[category].append(check_result)

    return {
        "categories": [{"category": cat, "checks": checks} for cat, checks in categories.items()]
    }


# extracted data comes in a nested structure, so we need to safely navigate through it to get the core fields
def map_api_data_to_invoice(invoice, api_response):
    """
    Map extracted invoice data (mock / OCR / API) to Invoice model
    """
    # Store full OCR response for this invoice
    invoice.raw_ocr_response = api_response

    # NESTED DATA EXTRACTION OR DATA ACCESS from data_gathering.py file

    invoice_data = (
        api_response
        .get("result", {})
        .get("Invoice_data", {})
    )
    

    # SAFE EXTRACTION
    core = extract_invoice_core_fields(api_response)
    vendor_name = invoice_data.get("VendorName")
    invoice_number = invoice_data.get("InvoiceId")
    invoice_value = invoice_data.get("InvoiceTotal")
    invoice_date_raw = core.get("invoice_date")          # step 2 : to get invoice date  
    

    if not invoice_date_raw:                              # step 1 : to get invoice date 
        invoice_date_raw = (
            invoice_data.get("InvoiceDate") 
            or invoice_data.get("InvoiceDate")
            or invoice_data.get("InvoiceDate")
        )


    # Dynamic Validations
    validation_summary = run_dynamic_validations(invoice_data)


    # step 3 : to get invoice date 
    def parse_invoice_date(value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        
        s = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
    
    parsed_invoice_date = parse_invoice_date(invoice_date_raw)
    
    # DEBUG: Print validation summary to verify all checks are running
    #import json
    #print("🔍 VALIDATION SUMMARY:")
    #print(json.dumps(validation_summary, indent=2))

    # UPDATE MODEL FIELDS
    if vendor_name:
        invoice.vendor_name = vendor_name

    if invoice_number:
        invoice.invoice_number = invoice_number

    if invoice_value:
        invoice.invoice_value = float(invoice_value)


    # Handle invoice date separately to ensure correct format
    if parsed_invoice_date:
        invoice.invoice_date = parsed_invoice_date

    invoice.validation_summary = validation_summary
    invoice.save()


    print("✅ INVOICE MAPPED:",
          invoice.vendor_name,
          invoice.invoice_number,
          invoice.invoice_value,
          invoice.invoice_date         
    )   
