from django.db import models
from django.contrib.auth.models import AbstractUser


# ====================================================== Company Details Model =====================================================
class CompanyDetails(models.Model):
    business_name = models.CharField(max_length=255)
    business_code = models.CharField(max_length=50)
    

    # Invoice Usage for Django Admin Dashboard Analytics
    max_invoices = models.IntegerField(default=100)
    
    def total_invoices(self):
        return self.invoices.count()
    
    def remaining_invoices(self):
        return max(0, self.max_invoices - self.total_invoices())
    
    def usage_percentage(self):
        if self.max_invoices <= 0:
            return 0
        return round((self.total_invoices() / self.max_invoices) * 100, 2)
    

    constitution = models.CharField(
        max_length=50,
        choices=[
            ('Public Ltd', 'Public Ltd'),
            ('Private Ltd', 'Private Ltd'),
            ('LLP', 'LLP'),
            ('Proprietorship', 'Proprietorship'),
            ('Partnership', 'Partnership'),
            ('Trust', 'Trust')
        ]
    )

    contact_person_name = models.CharField(max_length=255)
    
    country_code = models.CharField(
        max_length=10,
        choices=[
            ('+91', 'India (+91)'),
            ('+1', 'USA (+1)'),
            ('+44', 'UK (+44)'),
            ('+61', 'Australia (+61)'),
            ('+81', 'Japan (+81)'),
        ]
        )
    

    contact_person_number = models.CharField(max_length=20)
    contact_person_email = models.EmailField(unique=True)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    company_code = models.AutoField(primary_key=True)  # Auto-incremented unique code for the company
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # added pan field to store PAN number of the company for GST registration and compliance purposes
    pan = models.CharField(max_length=10)

    
    def __str__(self):
        return f"{self.business_name} ({self.contact_person_email})"


# ====================================================== Custom User Model ======================================================
class User(AbstractUser):
    company_code = models.ForeignKey(
        'CompanyDetails',  # Reference to your company model
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )
    
    ROLE_CHOICES = (
        ('APP_ADMIN', 'App Admin'),
        ('COMPANY_ADMIN', 'Company Admin'),
        ('PROCESSOR', 'Processor'),
    )  
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)


    status = models.CharField(max_length=20, null=True, blank=True)
    

    def __str__(self):
        return f"{self.username} ({self.role})"


# ====================================================== INVOICE MODEL ======================================================
class Invoice(models.Model):
    STATUS_CHOICES = [
        ('Standing', 'Standing'),
        ('Approved', 'Approved'),
        ('Accounted', 'Accounted'),
        ('Rejected', 'Rejected'),
        ('Hold', 'Hold'),
    ]
    
    company = models.ForeignKey(CompanyDetails, on_delete=models.CASCADE, related_name='invoices')
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_invoices')
    
    # Invoice details from BRD table headers
    vendor_name = models.CharField(max_length=255)
    invoice_number = models.CharField(max_length=100)
    invoice_date = models.DateField()
    invoice_value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # File details
    file_name = models.CharField(max_length=255)
    file_path = models.TextField()
    
    # Status and metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Standing')
    response = models.TextField(blank=True, null=True)  # Response column from BRD


    # validation summary to store results of dynamic validations (JSON structure)
    validation_summary = models.JSONField(null=True, blank=True)

    # Full OCR Response Storage
    raw_ocr_response = models.JSONField(null=True, blank=True)


    upload_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.vendor_name} - {self.invoice_number} ({self.status})"


# ====================================================== Invoice Remarks Model =======================================================
class InvoiceRemark(models.Model):
    """Stores processor remarks per invoice validation section and parameter."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='remarks')
    section = models.CharField(max_length=64)
    subsection = models.CharField(max_length=128)
    parameter_key = models.CharField(max_length=255)
    remark = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoice_remarks',
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_invoice_remarks',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = [['invoice', 'section', 'subsection', 'parameter_key']]

    def __str__(self):
        return f"Invoice {self.invoice_id} | {self.section}/{self.subsection} | {self.parameter_key}"


# ====================================================== GST Details Model =======================================================
class GSTDetails(models.Model):
    """
    Model to store GST registration details for each state where company is registered.
    Links to CompanyDetails (one company can have multiple GST registrations).
    """
    
    # List of Indian States & Union Territories (used as dropdown choices)
    # This ensures data consistency and avoids manual state name errors.

    INDIAN_STATES = [
        ('Andhra Pradesh', 'Andhra Pradesh'),
        ('Arunachal Pradesh', 'Arunachal Pradesh'),
        ('Assam', 'Assam'),
        ('Bihar', 'Bihar'),
        ('Chhattisgarh', 'Chhattisgarh'),
        ('Goa', 'Goa'),
        ('Gujarat', 'Gujarat'),
        ('Haryana', 'Haryana'),
        ('Himachal Pradesh', 'Himachal Pradesh'),
        ('Jharkhand', 'Jharkhand'),
        ('Karnataka', 'Karnataka'),
        ('Kerala', 'Kerala'),
        ('Madhya Pradesh', 'Madhya Pradesh'),
        ('Maharashtra', 'Maharashtra'),
        ('Manipur', 'Manipur'),
        ('Meghalaya', 'Meghalaya'),
        ('Mizoram', 'Mizoram'),
        ('Nagaland', 'Nagaland'),
        ('Odisha', 'Odisha'),
        ('Punjab', 'Punjab'),
        ('Rajasthan', 'Rajasthan'),
        ('Sikkim', 'Sikkim'),
        ('Tamil Nadu', 'Tamil Nadu'),
        ('Telangana', 'Telangana'),
        ('Tripura', 'Tripura'),
        ('Uttar Pradesh', 'Uttar Pradesh'),
        ('Uttarakhand', 'Uttarakhand'),
        ('West Bengal', 'West Bengal'),
        ('Delhi', 'Delhi'),
        ('Jammu and Kashmir', 'Jammu and Kashmir'),
        ('Ladakh', 'Ladakh'),
        ('Puducherry', 'Puducherry'),
        ('Chandigarh', 'Chandigarh'),
        ('Andaman and Nicobar Islands', 'Andaman and Nicobar Islands'),
        ('Dadra and Nagar Haveli and Daman and Diu', 'Dadra and Nagar Haveli and Daman and Diu'),
        ('Lakshadweep', 'Lakshadweep'),
    ]
    
    # Relationship Field
    # Each GST entry belongs to a specific company.
    # If company is deleted → GST records are also deleted (CASCADE).
    # related_name allows reverse access: company.gst_details.all()
    company = models.ForeignKey(
        CompanyDetails, 
        on_delete=models.CASCADE, 
        related_name='gst_details'
    )

    # State where GST is registered 
    state = models.CharField(max_length=100, choices=INDIAN_STATES)
    gst_number = models.CharField(max_length=15, help_text="15-digit GST Number")
    gst_address = models.TextField()
    
    # Optional GST portal credentials
    gst_portal_user_id = models.CharField(max_length=255, blank=True, null=True)
    gst_portal_password = models.CharField(max_length=255, blank=True, null=True, help_text="Encrypted password")
    
    # Status and audit trail
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_gst_details')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['state']
        unique_together = [['company', 'state']]  # One GST registration per state per company
        verbose_name = 'GST Detail'
        verbose_name_plural = 'GST Details'
    
    def __str__(self):
        return f"{self.company.business_name} - {self.state} ({self.gst_number})"


# ====================================================== HSN Master Model ======================================================
class HSN(models.Model):
    hsn_code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    block_credit = models.CharField(max_length=100, null=True, blank=True)  # BC / IC
    rcm = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.hsn_code
    

# ====================================================== SAC Master Model ======================================================
class SAC(models.Model):
    sac_code = models.CharField(max_length=20, unique=True)
    description = models.TextField()
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)
    block_credit = models.CharField(max_length=100, null=True, blank=True)  # BC / IC
    rcm = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.sac_code
    

# ====================================================== E-INVOICE REGISTER MODEL ======================================================  
class EInvoiceRegister(models.Model):
    supplier_gstin = models.CharField(max_length=20)
    document_number = models.CharField(max_length=50)
    document_date = models.DateField()
    supply_type = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    eway_bill_no = models.CharField(max_length=50, null=True, blank=True)
    irn = models.CharField(max_length=100, unique=True)
    irn_status = models.CharField(max_length=20)
    ack_no = models.CharField(max_length=50)   
    irn_date = models.DateTimeField()

    def __str__(self):
        return f"{self.document_number} - {self.irn}"
    
