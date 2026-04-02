from django import forms
from .models import CompanyDetails, GSTDetails, User
import re


class SignupForm(forms.ModelForm):
    class Meta:
        model = CompanyDetails
        # added pan field to the form for validation and input
        fields = ['business_name', 'business_code', 'constitution', 'contact_person_name', 
                  'country_code', 'contact_person_number', 'contact_person_email', 
                  'address_line1', 'address_line2' , 'pan']  
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        
        # Required fields (Backend Validation)
        self.fields['contact_person_name'].required = True
        self.fields['contact_person_number'].required = True
        self.fields['contact_person_email'].required = True
        self.fields['pan'].required = True    

        # Required fields (Frontend HTML Validation)  
        self.fields['contact_person_name'].widget.attrs.update({'required': True})
        self.fields['contact_person_number'].widget.attrs.update({'required': True})
        self.fields['contact_person_email'].widget.attrs.update({'required': True})
        self.fields['pan'].widget.attrs.update({'required': True})  
        self.fields['contact_person_number'].widget.attrs.update({'required': True,'maxlength': '10','pattern': '[0-9]{10}', 'title': 'Enter a valid 10 digit mobile number'})
       
        # PAN uppercase styling
        # Always converting PAN to uppercase
        self.fields['pan'].widget.attrs.update({
            'style': 'text-transform:uppercase'
        })
    

    # Pan validation method to ensure correct format 
    def clean_pan(self):
        pan = self.cleaned_data.get('pan')

        if pan:
            pan = pan.upper()
            pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'

            if not re.match(pattern, pan):
                raise forms.ValidationError("Invalid PAN format")

        return pan

    # Mobile number validation to ensure correct format
    def clean_contact_person_number(self):
        number = self.cleaned_data.get('contact_person_number')

        if number:
            number = number.strip()
        
            # Ensure only digits
            if not number.isdigit():
                raise forms.ValidationError("Contact number must contain only digits.")
        
            # Ensure length is 10 digits
            if len(number) != 10:
                raise forms.ValidationError("Mobile number must be exactly 10 digits.")
            
        return number
        



class GSTDetailsForm(forms.ModelForm):
    """
    Form for adding/editing GST registration details.
    Validates GST number format and handles optional portal credentials.
    """
    
    class Meta:
        model = GSTDetails
        fields = ['state', 'gst_number', 'gst_address', 'gst_portal_user_id', 'gst_portal_password', 'is_active']
        widgets = {
            'state': forms.Select(attrs={'class': 'form-control'}),

            'gst_number': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '15-digit GST Number (e.g., 27AABCU9603R1ZX)',
                'maxlength': '15'
            }),
            
            'gst_address': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3,
                'placeholder': 'Enter complete GST registered address'
            }),

            'gst_portal_user_id': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Optional - GST Portal Username'
            }),

            'gst_portal_password': forms.PasswordInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional - GST Portal Password',
                'autocomplete': 'new-password'
            }),

            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'state': 'State',
            'gst_number': 'GST Number',
            'gst_address': 'GST Registered Address',
            'gst_portal_user_id': 'GST Portal User ID (Optional)',
            'gst_portal_password': 'GST Portal Password (Optional)',
            'is_active': 'Active Status',
        }
    
    def clean_gst_number(self):
        """
        Validate GST number format: 15 characters, alphanumeric
        Format: 2 digits (state code) + 10 chars (PAN) + 1 char (entity number) + 1 char (Z) + 1 char (checksum)
        Example: 27AABCU9603R1ZX
        """
        gst_number = self.cleaned_data.get('gst_number', '').strip().upper()
        
        if not gst_number:
            raise forms.ValidationError("GST Number is required.")
        
        # Check length
        if len(gst_number) != 15:
            raise forms.ValidationError("GST Number must be exactly 15 characters.")
        
        # Check format using regex
        gst_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
        
        if not re.match(gst_pattern, gst_number):
            raise forms.ValidationError("Invalid GST Number format. Example: 27AABCU9603R1ZX")
        
        return gst_number
    
    def clean(self):
        """
        Validate that if portal user ID is provided, password must also be provided (and vice versa).
        This ensures credentials are complete when provided.
        """
        cleaned_data = super().clean()
        user_id = cleaned_data.get('gst_portal_user_id')
        password = cleaned_data.get('gst_portal_password')
        
        # If one is provided, both must be provided
        if (user_id and not password) or (password and not user_id):
            raise forms.ValidationError(
                "GST Portal credentials must be provided together. "
                "If you provide User ID, you must also provide Password (and vice versa)."
            )
        
        return cleaned_data



class UserManagementForm(forms.ModelForm):
    """
    Form for SuperUser to create/manage users in their company.
    Only Processor role available. Default status is Active.
    """
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 8 characters'}),
        min_length=8,
        help_text="Password must be at least 8 characters",
        label="Password"
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password'}),
        label="Confirm Password"
    )
    


    # Only Processor role available
    role = forms.ChoiceField(
        choices=[
            ('PROCESSOR', 'Processor'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Role",
        initial='PROCESSOR'
    )
    
    # Status with Active as default
    status = forms.ChoiceField(
        choices=[
            ('Active', 'Active'),
            ('Disabled', 'Disabled'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Status",
        initial='Active'
    )
    
    

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter full name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com'}),
        }
        labels = {
            'username': 'Name',
            'email': 'Email',
        }
    

    def clean_email(self):
        """Validate email is unique"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    

    def clean_username(self):
        """Validate username is not empty and reasonable length"""
        username = self.cleaned_data.get('username', '').strip()
        if not username:
            raise forms.ValidationError("Name is required.")
        if len(username) < 2:
            raise forms.ValidationError("Name must be at least 2 characters.")
        return username
    

    def clean_password(self):
        """Validate password strength"""
        password = self.cleaned_data.get('password')
        if password:
            if len(password) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long.")
            if password.isdigit():
                raise forms.ValidationError("Password cannot be entirely numeric.")
        return password
    

    def clean(self):
        """Validate passwords match"""
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
        
        return cleaned_data
    

    def save(self, commit=True, company=None):
        """Save user with hashed password, role, status and company assignment"""

        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])

        
        #user.role = self.cleaned_data['role']
        #user.status = self.cleaned_data['status']

        # Always set role to PROCESSOR (even if somehow overridden)
        user.role = 'PROCESSOR'
        
        # Get status, default to Active if somehow empty
        user.status = self.cleaned_data.get('status') or 'Active'
        
        if company:
            user.company_code = company
        
        if commit:
            user.save()
        
        return user



# Form for uploading E-Invoice Register Excel file
from django import forms
class EInvoiceUploadForm(forms.Form):
    file = forms.FileField()


