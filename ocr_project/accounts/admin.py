from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import Count
from .models import User, CompanyDetails
from django.utils.html import format_html

# UI Improvement 1 : Change 1 
from django.contrib.admin import SimpleListFilter


# Admin panel customization
admin.site.site_header = "App Admin Dashboard"
admin.site.site_title = "Admin Panel"
admin.site.index_title = "Welcome to App Admin Dashboard"


# UI Improvement 1 : Change 2
class RoleFilter(SimpleListFilter):
    title = 'Role'
    parameter_name = 'role'

    def lookups(self, request, model_admin):
        return [
            ('APP_ADMIN', '🔴 App Admin' ),
            ('COMPANY_ADMIN', '🟡 Company Admin'),
            ('PROCESSOR', '🟢 Processor'),
        ]
    
    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(role=self.value())
        return queryset


# UI Improvement 1 : Change 3
class ActiveFilter(SimpleListFilter):
    title = 'Activity Status'
    parameter_name = 'is_active'

    def lookups(self, request, model_admin):
        return [
            ('1', '✅ Active'),
            ('0', '❌ Inactive'),
        ]
    
    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(is_active=self.value() == '1')
        return queryset
    

class CustomUserCreationForm(UserCreationForm):
    """Creation form bound to the swapped custom user model."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role', 'company_code', 'is_active')


class CustomUserChangeForm(UserChangeForm):
    """Change form bound to the swapped custom user model."""

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


class CompanyAdminProcessorCreationForm(UserCreationForm):
    """Creation form used by company admins to add processor users only."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'is_active')


class UserAdmin(BaseUserAdmin):
    """Role-aware user administration for tenant isolation."""

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    def get_form(self, request, obj=None, **kwargs):
        # Company admins should not submit role/company fields from the add form.
        if obj is None and self._is_company_admin(request):
            kwargs['form'] = CompanyAdminProcessorCreationForm
        return super().get_form(request, obj, **kwargs)

    list_display = ('email', 'role_display', 'company_code', 'is_active_display', 'is_active')

    list_display_links = ('email',)
  
    list_editable = ('is_active',)

    search_fields = ('email', 'company_code__business_name')


    '''
    def get_list_filter(self, request):
        if self._is_app_admin(request):
            return ('role', 'is_active', 'company_code')
        if self._is_company_admin(request):
            return ('role', 'is_active')
        return ()
    '''

    # UI Improvement 1 : Change 4 
    def get_list_filter(self, request):
        if self._is_app_admin(request):
            return (RoleFilter, ActiveFilter, 'company_code')
        if self._is_company_admin(request):
            return (RoleFilter, ActiveFilter)
        return ()
    

    # Custom method to display role in a more user-fiendly way 
     
    def role_display(self, obj):
        color = {
            'APP_ADMIN': 'orange',
            'COMPANY_ADMIN': 'cream',
            'PROCESSOR': 'green',
        }.get(obj.role, 'black')
        
        return format_html(
            '<b style="color: {};">{}</b>',
            color,
            obj.role.replace("_", " ").title()
        )
    
    role_display.short_description = "Role"
    role_display.admin_order_field = "role"


    def is_active_display(self, obj):
        color = '#28a745' if obj.is_active else '#dc3545'
        label = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;">{}</span>',
            color,
            label,
        )

    is_active_display.short_description = 'Status'
    is_active_display.admin_order_field = 'is_active'


    def _role(self, request):
        return getattr(request.user, 'role', None)
    
    def _is_app_admin(self, request):
        return self._role(request) == 'APP_ADMIN'

    def _is_company_admin(self, request):
        return self._role(request) == 'COMPANY_ADMIN'

    def has_module_permission(self, request):
        return self._is_app_admin(request) or self._is_company_admin(request)

    def has_view_permission(self, request, obj=None):
        if self._is_app_admin(request):
            return True
        if self._is_company_admin(request):
            if obj is None:
                return True
            return obj.company_code_id == request.user.company_code_id
        return False

    def has_add_permission(self, request):
        return self._is_app_admin(request) or self._is_company_admin(request)

    def has_change_permission(self, request, obj=None):
        if self._is_app_admin(request):
            return True
        if self._is_company_admin(request):
            if obj is None:
                return True
            same_company = obj.company_code_id == request.user.company_code_id
            return same_company and obj.role == 'PROCESSOR'
        return False

    def has_delete_permission(self, request, obj=None):
        if self._is_app_admin(request):
            return True
        if self._is_company_admin(request) and obj is not None:
            same_company = obj.company_code_id == request.user.company_code_id
            return same_company and obj.role == 'PROCESSOR'
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._is_app_admin(request):
            return qs
        if self._is_company_admin(request):
            return qs.filter(company_code=request.user.company_code).exclude(role='APP_ADMIN')
        return qs.none()

    def get_exclude(self, request, obj=None):
        return ()

    def get_readonly_fields(self, request, obj=None):
        if self._is_company_admin(request):
            return ('role', 'company_code', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        return ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'company_code' and self._is_company_admin(request):
            kwargs['queryset'] = CompanyDetails.objects.filter(
                company_code=request.user.company_code_id
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == 'role':
            if self._is_company_admin(request):
                kwargs['choices'] = [('PROCESSOR', 'Processor')]
            elif self._is_app_admin(request):
                kwargs['choices'] = [
                    ('APP_ADMIN', 'App Admin'),
                    ('COMPANY_ADMIN', 'Company Admin'),
                    ('PROCESSOR', 'Processor'),
                ]
            else:
                kwargs['choices'] = []
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_fieldsets(self, request, obj=None):
        # Ensure the add page uses add-specific fields/forms.
        if obj is None:
            return self.get_add_fieldsets(request)

        if self._is_app_admin(request):
            return (
                ('User Info', {'fields': ('username', 'email', 'password')}),
                ('Role and Company', {'fields': ('role', 'company_code')}),
                ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )

        if self._is_company_admin(request):
            return (
                ('User Info', {'fields': ('username', 'email', 'password')}),
                ('Processor Access', {'fields': ('is_active',)}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )

        return ()

    def get_add_fieldsets(self, request):
        if self._is_app_admin(request):
            return (
                (None, {
                    'classes': ('wide',),
                    'fields': ('username', 'email', 'password1', 'password2', 'role', 'company_code', 'is_active'),
                }),
            )

        if self._is_company_admin(request):
            return (
                (None, {
                    'classes': ('wide',),
                    'fields': ('username', 'email', 'password1', 'password2', 'is_active'),
                }),
            )

        return ()

    def save_model(self, request, obj, form, change):
        if self._is_company_admin(request):
            # Hard enforce tenant and role at save time (server-side).
            obj.role = 'PROCESSOR'
            obj.company_code = request.user.company_code
            if not obj.status:
                obj.status = 'Active'
            obj.is_staff = False
            obj.is_superuser = False
        elif self._is_app_admin(request):
            # Keep Django admin flags aligned with business role.
            if obj.role == 'APP_ADMIN':
                obj.is_staff = True
            elif obj.role == 'COMPANY_ADMIN':
                obj.is_staff = True
                obj.is_superuser = False
            elif obj.role == 'PROCESSOR':
                if not obj.status:
                    obj.status = 'Active'
                obj.is_staff = False
                obj.is_superuser = False

        super().save_model(request, obj, form, change)


admin.site.register(User, UserAdmin)


#---------------------------------------------------------------------------------------------------------------------------------------

# CompanyAdmin with tenant isolation and role-based access control
class CompanyAdmin(admin.ModelAdmin):
    """Tenant-aware company administration."""

    list_display = (
        'company_code',
        'business_name',
        'contact_person_email',
        'max_invoices',
        'total_invoices_display',
        'remaining_invoices_display',
        'usage_meter',
        'updated_at',
    )
    

    search_fields = ('business_name', 'contact_person_email', 'business_code')
    readonly_fields = (
        'company_code',
        'total_invoices_display',
        'remaining_invoices_display',
        'usage_meter',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        (
            'Company Profile',
            {
                'fields': (
                    'business_name', 'business_code', 'constitution',
                    'contact_person_name', 'country_code', 'contact_person_number',
                    'contact_person_email', 'address_line1', 'address_line2', 'pan',
                )
            },
        ),
        (
            'Invoice Usage',
            {
                'fields': (
                    'max_invoices', 'total_invoices_display',
                    'remaining_invoices_display', 'usage_meter',
                )
            },
        ),
        (
            'Audit',
            {
                'fields': ('company_code', 'created_at', 'updated_at')
            },
        ),
    )

    def total_invoices_display(self, obj):
        return getattr(obj, 'invoice_count', obj.total_invoices())
    total_invoices_display.short_description = 'Invoices Used'

    def remaining_invoices_display(self, obj):
        return max(0, obj.max_invoices - getattr(obj, 'invoice_count', obj.total_invoices()))
    #remaining_invoices_display.short_description = 'Invoices Left'
    remaining_invoices_display.short_description = 'Remaining'

    def usage_meter(self, obj):
        used = getattr(obj, 'invoice_count', obj.total_invoices())
        limit = obj.max_invoices or 0
        percent = 0 if limit <= 0 else round((used / limit) * 100, 2)
        width = min(percent, 100)
        color = '#dc3545' if percent >= 100 else '#28a745'
        return format_html(
            '<div style="min-width:180px;">'
            '  <div style="height:10px;background:#e9ecef;border-radius:999px;overflow:hidden;">'
            '    <div style="width:{}%;height:10px;background:{};"></div>'
            '  </div>'
            '  <small>{}% (Used: {} of {})</small>'
            '</div>',
            width,
            color,
            percent,
            used,
            limit,
        )
    usage_meter.short_description = 'Usage'

    def has_module_permission(self, request):
        if not request.user.is_authenticated:
            return False

        return request.user.role in ['APP_ADMIN', 'COMPANY_ADMIN']

    def has_view_permission(self, request, obj=None):
        if request.user.role == 'APP_ADMIN':
            return True
        if request.user.role == 'COMPANY_ADMIN':
            if obj is None:
                return True 
            return obj.company_code == request.user.company_code_id
        return False

    def has_add_permission(self, request):
        # Only app admin can create tenants.
        return request.user.role == 'APP_ADMIN'

    def has_change_permission(self, request, obj=None):
        if request.user.role == 'APP_ADMIN':
            return True
        if request.user.role == 'COMPANY_ADMIN':
            if obj is None:
                return True
            return obj.company_code == request.user.company_code_id
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.role == 'APP_ADMIN'

    def get_queryset(self, request):
        qs = super().get_queryset(request).annotate(invoice_count=Count('invoices'))

        if request.user.role == 'APP_ADMIN':
            return qs
        if request.user.role == 'COMPANY_ADMIN':
            return qs.filter(company_code=request.user.company_code_id)
        return qs.none()

admin.site.register(CompanyDetails, CompanyAdmin)

