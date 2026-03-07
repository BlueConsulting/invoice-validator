from django.db import models
from django.contrib.auth.models import AbstractUser

# Company Details Model
class CompanyDetails(models.Model):
    business_name = models.CharField(max_length=255)
    business_code = models.CharField(max_length=50)
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

    
    def __str__(self):
        return f"{self.business_name} ({self.contact_person_email})"


# Custom User Model
class User(AbstractUser):
    company_code = models.ForeignKey(
        'CompanyDetails',  # Reference to your company model
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )
    role = models.CharField(max_length=20)  # Role (e.g., Admin, Manager, Employee)
    status = models.CharField(max_length=20, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


# Invoice Model 
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



# GST Details Model 
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