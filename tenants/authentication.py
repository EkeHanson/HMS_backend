from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone

from .models import TenantUser


class TenantAuthenticationBackend(ModelBackend):
    """Authentication backend for tenant users."""
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Get tenant from request
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return None
        
        try:
            # Get tenant user
            user = TenantUser.objects.get(
                username=username,
                tenant=tenant,
                is_active=True
            )
            
            # Check password
            if user.check_password(password):
                # Check if account is locked
                if user.is_account_locked():
                    return None
                
                # Reset failed login attempts
                user.failed_login_attempts = 0
                user.account_locked_until = None
                user.last_login = timezone.now()
                user.last_login_ip = self.get_client_ip(request)
                user.save()
                
                return user
        
        except TenantUser.DoesNotExist:
            # User doesn't exist in this tenant
            # Record failed attempt if user exists
            try:
                user = TenantUser.objects.get(username=username, tenant=tenant)
                user.failed_login_attempts += 1
                
                # Lock account after 5 failed attempts
                if user.failed_login_attempts >= 5:
                    user.lock_account(30)
                
                user.save()
            except TenantUser.DoesNotExist:
                pass
        
        return None
    
    def get_user(self, user_id):
        try:
            return TenantUser.objects.get(pk=user_id)
        except TenantUser.DoesNotExist:
            return None
    
    def get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class HybridAuthenticationBackend:
    """Hybrid authentication backend supporting both global and tenant users."""
    
    def __init__(self):
        self.global_backend = ModelBackend()
        self.tenant_backend = TenantAuthenticationBackend()
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Try global users first
        user = self.global_backend.authenticate(request, username, password, **kwargs)
        if user:
            request.is_global_user = True
            return user
        
        # Try tenant users
        user = self.tenant_backend.authenticate(request, username, password, **kwargs)
        if user:
            request.is_global_user = False
            return user
        
        return None
    
    def get_user(self, user_id):
        # Try global user first
        user = self.global_backend.get_user(user_id)
        if user:
            return user
        
        # Try tenant user
        return self.tenant_backend.get_user(user_id)