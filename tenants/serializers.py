from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.utils import timezone
import re

from .models import (
    Tenant, SubscriptionPlan, TenantUser, Department,
    TenantSetting, TenantModule, TenantInvitation,
    TenantActivityLog, TenantBackup
)
from core.models import State, LGA, FacilityType
from core.serializers import StateSerializer, LGASerializer, FacilityTypeSerializer


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for subscription plans."""
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for tenants."""
    state_details = StateSerializer(source='state', read_only=True)
    lga_details = LGASerializer(source='lga', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    facility_type_details = FacilityTypeSerializer(source='facility_type', read_only=True)
    subscription_plan_details = SubscriptionPlanSerializer(source='subscription_plan', read_only=True)
    
    # Computed fields
    is_active_status = serializers.BooleanField(source='is_active', read_only=True)
    days_remaining_in_trial = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Tenant
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at', 'code', 'schema_name',
            'subscription_status', 'created_by'
        ]
    
    def validate_domain(self, value):
        """Validate domain format."""
        # Simple domain validation
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
        if not re.match(domain_pattern, value):
            raise serializers.ValidationError("Invalid domain format")
        return value.lower()
    
    def validate_registration_number(self, value):
        """Validate registration number format."""
        # Add specific validation for Nigerian registration numbers if needed
        return value.upper()
    
    def create(self, validated_data):
        # Set created_by from request user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['created_by'] = request.user
        
        # Create tenant
        tenant = Tenant.objects.create(**validated_data)
        
        # Create default settings
        TenantSetting.objects.create(tenant=tenant)
        
        # Create default departments
        self.create_default_departments(tenant)
        
        return tenant
    
    def create_default_departments(self, tenant):
        """Create default departments for a new tenant."""
        default_departments = [
            {'name': 'Administration', 'code': 'ADMIN', 'is_clinical': False},
            {'name': 'Outpatient Department', 'code': 'OPD', 'is_clinical': True},
            {'name': 'Inpatient Department', 'code': 'IPD', 'is_clinical': True},
            {'name': 'Emergency Department', 'code': 'ER', 'is_clinical': True},
            {'name': 'Pharmacy', 'code': 'PHARM', 'is_clinical': False},
            {'name': 'Laboratory', 'code': 'LAB', 'is_clinical': False},
            {'name': 'Radiology', 'code': 'RAD', 'is_clinical': False},
            {'name': 'Billing', 'code': 'BILL', 'is_clinical': False},
            {'name': 'Human Resources', 'code': 'HR', 'is_clinical': False},
        ]
        
        for dept_data in default_departments:
            Department.objects.create(tenant=tenant, **dept_data)


class TenantUserSerializer(serializers.ModelSerializer):
    """Serializer for tenant users."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    tenant_code = serializers.CharField(source='tenant.code', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    state_name = serializers.CharField(source='state.name', read_only=True)
    full_name = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = TenantUser
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at', 'last_login',
            'last_login_ip', 'password_changed_at',
            'failed_login_attempts', 'account_locked_until'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
            'username': {'required': True},
        }
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def validate_email(self, value):
        """Validate email format and uniqueness within tenant."""
        try:
            validate_email(value)
        except:
            raise serializers.ValidationError("Invalid email format")
        
        # Check uniqueness within tenant
        tenant = self.context.get('tenant')
        if tenant:
            if TenantUser.objects.filter(tenant=tenant, email=value).exists():
                raise serializers.ValidationError("Email already exists in this tenant")
        
        return value.lower()
    
    def validate_username(self, value):
        """Validate username uniqueness within tenant."""
        tenant = self.context.get('tenant')
        if tenant:
            if TenantUser.objects.filter(tenant=tenant, username=value).exists():
                raise serializers.ValidationError("Username already exists in this tenant")
        return value
    
    def validate_password(self, value):
        """Validate password strength."""
        if value:
            validate_password(value)
        return value
    
    def create(self, validated_data):
        # Get tenant from context or request body
        tenant = self.context.get('tenant')
        
        # If tenant not in context, try to get from request data
        if not tenant:
            tenant_id = self.context.get('request').data.get('tenant') if self.context.get('request') else None
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=int(tenant_id))
                except (Tenant.DoesNotExist, ValueError):
                    raise serializers.ValidationError({"tenant": ["Invalid tenant"]})
        
        if not tenant:
            raise serializers.ValidationError({"tenant": ["This field is required."]})
        
        # Remove tenant from validated_data if present (to avoid duplicate)
        validated_data.pop('tenant', None)
        
        # Extract password
        password = validated_data.pop('password', None)
        
        # Create user
        user = TenantUser.objects.create(tenant=tenant, **validated_data)
        
        # Set password if provided
        if password:
            user.set_password(password)
            user.save()
        
        return user
    
    def update(self, instance, validated_data):
        # Handle password update
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for departments."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    head_name = serializers.CharField(source='head.get_full_name', read_only=True)
    
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TenantSettingSerializer(serializers.ModelSerializer):
    """Serializer for tenant settings."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = TenantSetting
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def validate_tax_rate(self, value):
        """Validate tax rate (0-100%)."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Tax rate must be between 0 and 100")
        return value
    
    def validate_session_timeout(self, value):
        """Validate session timeout (5-1440 minutes)."""
        if value < 5 or value > 1440:
            raise serializers.ValidationError("Session timeout must be between 5 and 1440 minutes")
        return value


class TenantModuleSerializer(serializers.ModelSerializer):
    """Serializer for tenant modules."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = TenantModule
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TenantInvitationSerializer(serializers.ModelSerializer):
    """Serializer for tenant invitations."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    invited_by_name = serializers.CharField(source='invited_by.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = TenantInvitation
        fields = '__all__'
        read_only_fields = [
            'created_at', 'updated_at', 'token',
            'sent_at', 'accepted_at', 'status'
        ]
    
    def validate_email(self, value):
        """Validate email and check if already a user."""
        try:
            validate_email(value)
        except:
            raise serializers.ValidationError("Invalid email format")
        
        # Check if user already exists in tenant
        tenant = self.context.get('tenant')
        if tenant and TenantUser.objects.filter(tenant=tenant, email=value).exists():
            raise serializers.ValidationError("User with this email already exists in the tenant")
        
        # Check for pending invitation
        if tenant:
            pending_invite = TenantInvitation.objects.filter(
                tenant=tenant,
                email=value,
                status=TenantInvitation.InvitationStatus.PENDING
            ).exists()
            if pending_invite:
                raise serializers.ValidationError("Pending invitation already exists for this email")
        
        return value.lower()


class AcceptInvitationSerializer(serializers.Serializer):
    """Serializer for accepting tenant invitations."""
    token = serializers.CharField(required=True)
    username = serializers.CharField(required=True)
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        # Check if passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        
        # Validate password strength
        validate_password(data['password'])
        
        # Check invitation
        token = data['token']
        try:
            invitation = TenantInvitation.objects.get(
                token=token,
                status=TenantInvitation.InvitationStatus.PENDING
            )
        except TenantInvitation.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid or expired invitation"})
        
        if invitation.is_expired():
            invitation.status = TenantInvitation.InvitationStatus.EXPIRED
            invitation.save()
            raise serializers.ValidationError({"token": "Invitation has expired"})
        
        data['invitation'] = invitation
        return data
    
    def save(self, **kwargs):
        invitation = self.validated_data['invitation']
        
        # Create user from invitation
        user_data = {
            'username': self.validated_data['username'],
            'first_name': self.validated_data['first_name'],
            'last_name': self.validated_data['last_name'],
            'password': self.validated_data['password'],
        }
        
        return invitation.accept(user_data)


class TenantActivityLogSerializer(serializers.ModelSerializer):
    """Serializer for tenant activity logs."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = TenantActivityLog
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class TenantBackupSerializer(serializers.ModelSerializer):
    """Serializer for tenant backups."""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = TenantBackup
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return None


class TenantSummarySerializer(serializers.ModelSerializer):
    """Serializer for tenant summary statistics."""
    user_count = serializers.IntegerField(read_only=True)
    patient_count = serializers.IntegerField(read_only=True)
    department_count = serializers.IntegerField(read_only=True)
    active_modules_count = serializers.IntegerField(read_only=True)
    storage_used_mb = serializers.FloatField(read_only=True)
    last_backup_time = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'code', 'domain', 'subscription_status',
            'subscription_plan', 'user_count', 'patient_count',
            'department_count', 'active_modules_count',
            'storage_used_mb', 'last_backup_time'
        ]