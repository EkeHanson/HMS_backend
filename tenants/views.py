from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.conf import settings

from .models import (
    Tenant, SubscriptionPlan, TenantUser, Department,
    TenantSetting, TenantModule, TenantInvitation,
    TenantActivityLog, TenantBackup
)
from .serializers import (
    TenantSerializer, SubscriptionPlanSerializer, TenantUserSerializer,
    DepartmentSerializer, TenantSettingSerializer, TenantModuleSerializer,
    TenantInvitationSerializer, AcceptInvitationSerializer,
    TenantActivityLogSerializer, TenantBackupSerializer, TenantSummarySerializer
)
from core.permissions import IsSystemAdmin
from core.models import AuditLog


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db import connection


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# Public endpoint for listing active tenants (for login page)
class PublicTenantListView(APIView):
    """Public endpoint to list active tenants for login page."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # No authentication required
    
    def get(self, request):
        # Reset to public schema before querying
        from django.db import connection
        connection.set_schema('public')
        
        tenants = Tenant.objects.filter(
            subscription_status__in=['active', 'trial']
        ).only('id', 'name', 'code', 'domain', 'logo')
        
        data = [
            {
                'id': t.id,
                'name': t.name,
                'code': t.code,
                'domain': t.domain,
            }
            for t in tenants
        ]
        return Response(data)



class TenantViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenants (global admin only)."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    pagination_class = StandardPagination
    permission_classes = [IsSystemAdmin]
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter by subscription status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            self.queryset = self.queryset.filter(subscription_status=status_filter)
        
        # Filter by NHIS accreditation
        nhis_filter = self.request.query_params.get('nhis_accreditation')
        if nhis_filter:
            self.queryset = self.queryset.filter(nhis_accreditation=nhis_filter)
        
        # Search by name, code, or domain
        search = self.request.query_params.get('search')
        if search:
            self.queryset = self.queryset.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(domain__icontains=search) |
                Q(email__icontains=search)
            )
        
        return self.queryset
    
    def perform_create(self, serializer):
        with transaction.atomic():
            # Create tenant
            tenant = serializer.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=self.request.user,
                action='create_tenant',
                resource_type='tenant',
                resource_id=str(tenant.id),
                new_values=serializer.data
            )
            
            # Create initial admin user
            admin_data = {
                'username': f"admin@{tenant.domain.split('.')[0]}",
                'email': tenant.email,
                'first_name': 'Admin',
                'last_name': tenant.name,
                'role': 'admin',
                'password': 'TempPass123!',
                'is_staff': True,
            }
            
            admin_user = TenantUser.objects.create(
                tenant=tenant,
                **admin_data
            )
            admin_user.set_password(admin_data['password'])
            admin_user.save()
    
    def perform_update(self, serializer):
        old_tenant = self.get_object()
        old_data = TenantSerializer(old_tenant).data
        
        tenant = serializer.save()
        
        # Log the action
        AuditLog.objects.create(
            user=self.request.user,
            action='update_tenant',
            resource_type='tenant',
            resource_id=str(tenant.id),
            old_values=old_data,
            new_values=serializer.data
        )
    
    def perform_destroy(self, instance):
        tenant_id = instance.id
        tenant_name = instance.name
        
        # Log before deletion
        AuditLog.objects.create(
            user=self.request.user,
            action='delete_tenant',
            resource_type='tenant',
            resource_id=str(tenant_id),
            old_values={'name': tenant_name}
        )
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Suspend a tenant."""
        tenant = self.get_object()
        tenant.subscription_status = Tenant.SubscriptionStatus.SUSPENDED
        tenant.is_active = False
        tenant.save()
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='suspend_tenant',
            resource_type='tenant',
            resource_id=str(tenant.id),
            new_values={'subscription_status': 'suspended', 'is_active': False}
        )
        
        return Response({'detail': 'Tenant suspended successfully'})
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a tenant."""
        tenant = self.get_object()
        tenant.subscription_status = Tenant.SubscriptionStatus.ACTIVE
        tenant.is_active = True
        tenant.save()
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='activate_tenant',
            resource_type='tenant',
            resource_id=str(tenant.id),
            new_values={'subscription_status': 'active', 'is_active': True}
        )
        
        return Response({'detail': 'Tenant activated successfully'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel tenant subscription."""
        tenant = self.get_object()
        tenant.subscription_status = Tenant.SubscriptionStatus.CANCELLED
        tenant.is_active = False
        tenant.save()
        
        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='cancel_tenant',
            resource_type='tenant',
            resource_id=str(tenant.id),
            new_values={'subscription_status': 'cancelled', 'is_active': False}
        )
        
        return Response({'detail': 'Tenant subscription cancelled'})
    
    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Get tenant summary statistics."""
        tenant = self.get_object()
        
        # Get statistics
        user_count = TenantUser.objects.filter(tenant=tenant).count()
        # patient_count = Patient.objects.filter(tenant=tenant).count()  # Will be added later
        patient_count = 0
        department_count = Department.objects.filter(tenant=tenant).count()
        active_modules_count = TenantModule.objects.filter(
            tenant=tenant, is_enabled=True
        ).count()
        
        # Get last backup
        last_backup = TenantBackup.objects.filter(
            tenant=tenant,
            status=TenantBackup.BackupStatus.COMPLETED
        ).order_by('-created_at').first()
        
        data = {
            'id': tenant.id,
            'name': tenant.name,
            'code': tenant.code,
            'domain': tenant.domain,
            'subscription_status': tenant.subscription_status,
            'subscription_plan': tenant.subscription_plan.id if tenant.subscription_plan else None,
            'user_count': user_count,
            'patient_count': patient_count,
            'department_count': department_count,
            'active_modules_count': active_modules_count,
            'storage_used_mb': 0,  # Will be calculated from storage
            'last_backup_time': last_backup.created_at if last_backup else None,
        }
        
        serializer = TenantSummarySerializer(data=data)
        serializer.is_valid()
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get global tenant statistics."""
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(
            subscription_status=Tenant.SubscriptionStatus.ACTIVE,
            is_active=True
        ).count()
        trial_tenants = Tenant.objects.filter(
            subscription_status=Tenant.SubscriptionStatus.TRIAL
        ).count()
        suspended_tenants = Tenant.objects.filter(
            subscription_status=Tenant.SubscriptionStatus.SUSPENDED
        ).count()
        
        # Monthly revenue projection
        active_tenants_revenue = Tenant.objects.filter(
            subscription_status=Tenant.SubscriptionStatus.ACTIVE
        ).aggregate(total=Sum('monthly_fee'))['total'] or 0
        
        # Tenants by facility type
        tenants_by_type = Tenant.objects.values(
            'facility_type__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Tenants by state
        tenants_by_state = Tenant.objects.values(
            'state__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        return Response({
            'total_tenants': total_tenants,
            'active_tenants': active_tenants,
            'trial_tenants': trial_tenants,
            'suspended_tenants': suspended_tenants,
            'monthly_revenue': float(active_tenants_revenue),
            'tenants_by_facility_type': list(tenants_by_type),
            'tenants_by_state': list(tenants_by_state),
        })




@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_tenant_admin(request, tenant_id):
    try:
        tenant = Tenant.objects.get(id=tenant_id)

        data = request.data
        admin_user = TenantUser.objects.create(
            tenant=tenant,
            username=data['username'],
            email=data['email'],
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone=data.get('phone', ''),
            role='admin',
            employee_id=data.get('employee_id', ''),
            is_staff=True,
            is_active=True
        )
        admin_user.set_password(data['password'])
        admin_user.save()

        return Response({
            'message': 'Tenant admin created successfully',
            'user': {
                'id': admin_user.id,
                'username': admin_user.username,
                'email': admin_user.email,
                'tenant_id': tenant.id,
                'tenant_name': tenant.name
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """ViewSet for managing subscription plans."""
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    pagination_class = StandardPagination
    permission_classes = [IsSystemAdmin]
    
    def perform_create(self, serializer):
        plan = serializer.save()
        
        # Log action
        AuditLog.objects.create(
            user=self.request.user,
            action='create_subscription_plan',
            resource_type='subscription_plan',
            resource_id=str(plan.id),
            new_values=serializer.data
        )
    
    def perform_update(self, serializer):
        old_plan = self.get_object()
        old_data = SubscriptionPlanSerializer(old_plan).data
        
        plan = serializer.save()
        
        # Log action
        AuditLog.objects.create(
            user=self.request.user,
            action='update_subscription_plan',
            resource_type='subscription_plan',
            resource_id=str(plan.id),
            old_values=old_data,
            new_values=serializer.data
        )
    
    def perform_destroy(self, instance):
        plan_id = instance.id
        plan_name = instance.name
        
        # Log before deletion
        AuditLog.objects.create(
            user=self.request.user,
            action='delete_subscription_plan',
            resource_type='subscription_plan',
            resource_id=str(plan_id),
            old_values={'name': plan_name}
        )
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set a subscription plan as default."""
        plan = self.get_object()
        
        # Remove default from other plans
        SubscriptionPlan.objects.filter(is_default=True).update(is_default=False)
        
        # Set this plan as default
        plan.is_default = True
        plan.save()
        
        return Response({'detail': f'{plan.name} set as default plan'})


class TenantUserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenant users."""
    serializer_class = TenantUserSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # If global admin, can view all tenant users
        if user.is_superuser or user.role == 'super_admin' or user.role == 'system_admin':
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return TenantUser.objects.filter(tenant_id=tenant_id)
            return TenantUser.objects.all()
        
        # If tenant user with global access
        if hasattr(user, 'tenant_user') and user.tenant_user:
            tenant = user.tenant_user.tenant
            
            # Filter by role
            role_filter = self.request.query_params.get('role')
            if role_filter:
                return TenantUser.objects.filter(tenant=tenant, role=role_filter)
            
            # Search
            search = self.request.query_params.get('search')
            if search:
                return TenantUser.objects.filter(
                    tenant=tenant,
                    # Q(username__icontains=search) |
                    # Q(email__icontains=search) |
                    # Q(first_name__icontains=search) |
                    # Q(last_name__icontains=search)
                )
            
            return TenantUser.objects.filter(tenant=tenant)
        
        return TenantUser.objects.none()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        
        # Add tenant to context if available
        user = self.request.user
        if hasattr(user, 'tenant_user') and user.tenant_user:
            context['tenant'] = user.tenant_user.tenant
        
        return context
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            # Only tenant admins or global admins can modify users
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        user = self.request.user
        
        # Check permissions
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant user creating another tenant user
            if user.tenant_user.role not in ['admin', 'hr_manager']:
                raise permissions.PermissionDenied("Only admins and HR managers can create users")
        
        serializer.save()
    
    @action(detail=True, methods=['post'])
    def lock_account(self, request, pk=None):
        """Lock user account."""
        user = self.get_object()
        duration = request.data.get('duration_minutes', 30)
        
        # Check permissions
        request_user = request.user
        if hasattr(request_user, 'tenant_user') and request_user.tenant_user:
            if request_user.tenant_user.role not in ['admin']:
                raise permissions.PermissionDenied("Only admins can lock accounts")
        
        user.lock_account(duration)
        
        return Response({'detail': f'Account locked for {duration} minutes'})
    
    @action(detail=True, methods=['post'])
    def unlock_account(self, request, pk=None):
        """Unlock user account."""
        user = self.get_object()
        
        # Check permissions
        request_user = request.user
        if hasattr(request_user, 'tenant_user') and request_user.tenant_user:
            if request_user.tenant_user.role not in ['admin']:
                raise permissions.PermissionDenied("Only admins can unlock accounts")
        
        user.unlock_account()
        
        return Response({'detail': 'Account unlocked'})


class DepartmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing departments."""
    serializer_class = DepartmentSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            tenant = user.tenant_user.tenant
            
            # Filter by clinical/non-clinical
            is_clinical = self.request.query_params.get('is_clinical')
            if is_clinical is not None:
                return Department.objects.filter(
                    tenant=tenant,
                    is_clinical=is_clinical.lower() == 'true'
                )
            
            return Department.objects.filter(tenant=tenant)
        
        # Global admin can see all departments
        if user.is_superuser or user.role in ['super_admin', 'system_admin']:
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return Department.objects.filter(tenant_id=tenant_id)
            return Department.objects.all()
        
        return Department.objects.none()
    
    def perform_create(self, serializer):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Only admins and HR managers can create departments
            if user.tenant_user.role not in ['admin', 'hr_manager']:
                raise permissions.PermissionDenied("Only admins and HR managers can create departments")
            
            # Set tenant from current user
            serializer.save(tenant=user.tenant_user.tenant)
        else:
            # Global admin creating department
            serializer.save()


class TenantSettingViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenant settings."""
    serializer_class = TenantSettingSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant user can only see their tenant's settings
            return TenantSetting.objects.filter(tenant=user.tenant_user.tenant)
        
        # Global admin can see all settings
        if user.is_superuser or user.role in ['super_admin', 'system_admin']:
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return TenantSetting.objects.filter(tenant_id=tenant_id)
            return TenantSetting.objects.all()
        
        return TenantSetting.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            # Only global admins can create/delete settings
            return [IsSystemAdmin()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current tenant's settings."""
        user = request.user
        
        if not hasattr(user, 'tenant_user') or not user.tenant_user:
            raise permissions.PermissionDenied("Not a tenant user")
        
        settings = get_object_or_404(TenantSetting, tenant=user.tenant_user.tenant)
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


class TenantModuleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenant modules."""
    serializer_class = TenantModuleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant user can only see their tenant's modules
            return TenantModule.objects.filter(tenant=user.tenant_user.tenant)
        
        # Global admin can see all modules
        if user.is_superuser or user.role in ['super_admin', 'system_admin']:
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return TenantModule.objects.filter(tenant_id=tenant_id)
            return TenantModule.objects.all()
        
        return TenantModule.objects.none()
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """Enable a module."""
        module = self.get_object()
        
        # Check permissions
        user = request.user
        if hasattr(user, 'tenant_user') and user.tenant_user:
            if user.tenant_user.role not in ['admin']:
                raise permissions.PermissionDenied("Only admins can enable/disable modules")
        
        module.is_enabled = True
        module.enabled_date = timezone.now()
        module.disabled_date = None
        module.save()
        
        return Response({'detail': 'Module enabled'})
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """Disable a module."""
        module = self.get_object()
        
        # Check permissions
        user = request.user
        if hasattr(user, 'tenant_user') and user.tenant_user:
            if user.tenant_user.role not in ['admin']:
                raise permissions.PermissionDenied("Only admins can enable/disable modules")
        
        module.is_enabled = False
        module.disabled_date = timezone.now()
        module.save()
        
        return Response({'detail': 'Module disabled'})


class TenantInvitationViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenant invitations."""
    serializer_class = TenantInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant user can see invitations for their tenant
            return TenantInvitation.objects.filter(tenant=user.tenant_user.tenant)
        
        return TenantInvitation.objects.none()
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        
        # Add tenant to context
        user = self.request.user
        if hasattr(user, 'tenant_user') and user.tenant_user:
            context['tenant'] = user.tenant_user.tenant
        
        return context
    
    def perform_create(self, serializer):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Only admins and HR managers can send invitations
            if user.tenant_user.role not in ['admin', 'hr_manager']:
                raise permissions.PermissionDenied("Only admins and HR managers can send invitations")
            
            # Set invited_by and tenant
            serializer.save(
                invited_by=user.tenant_user,
                tenant=user.tenant_user.tenant
            )
    
    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """Resend an invitation."""
        invitation = self.get_object()
        
        # Check if invitation is pending
        if invitation.status != TenantInvitation.InvitationStatus.PENDING:
            return Response(
                {'error': 'Cannot resend non-pending invitation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update expiry (extend by 7 days)
        invitation.expires_at = timezone.now() + timezone.timedelta(days=7)
        invitation.save()
        
        # TODO: Send email with invitation link
        
        return Response({'detail': 'Invitation resent'})
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke an invitation."""
        invitation = self.get_object()
        invitation.status = TenantInvitation.InvitationStatus.REVOKED
        invitation.save()
        
        return Response({'detail': 'Invitation revoked'})




class AcceptInvitationView(APIView):
    """Accept a tenant invitation."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = AcceptInvitationSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            
            # Return user data
            user_serializer = TenantUserSerializer(user)
            return Response({
                'detail': 'Invitation accepted successfully',
                'user': user_serializer.data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class TenantActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing tenant activity logs."""
    serializer_class = TenantActivityLogSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant user can see their tenant's activity logs
            return TenantActivityLog.objects.filter(tenant=user.tenant_user.tenant)
        
        # Global admin can see all activity logs
        if user.is_superuser or user.role in ['super_admin', 'system_admin']:
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return TenantActivityLog.objects.filter(tenant_id=tenant_id)
            return TenantActivityLog.objects.all()
        
        return TenantActivityLog.objects.none()
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get activity log summary."""
        user = request.user
        
        if not hasattr(user, 'tenant_user') or not user.tenant_user:
            raise permissions.PermissionDenied("Not a tenant user")
        
        tenant = user.tenant_user.tenant
        
        # Get activity counts by user
        activity_by_user = TenantActivityLog.objects.filter(
            tenant=tenant
        ).values(
            'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Get activity counts by action
        activity_by_action = TenantActivityLog.objects.filter(
            tenant=tenant
        ).values('action').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Get recent activities
        recent_activities = TenantActivityLog.objects.filter(
            tenant=tenant
        ).select_related('user').order_by('-created_at')[:20]
        
        recent_serializer = self.get_serializer(recent_activities, many=True)
        
        return Response({
            'activity_by_user': list(activity_by_user),
            'activity_by_action': list(activity_by_action),
            'recent_activities': recent_serializer.data,
        })


class TenantBackupViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tenant backups."""
    serializer_class = TenantBackupSerializer
    pagination_class = StandardPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if hasattr(user, 'tenant_user') and user.tenant_user:
            # Tenant admin can see their tenant's backups
            if user.tenant_user.role == 'admin':
                return TenantBackup.objects.filter(tenant=user.tenant_user.tenant)
        
        # Global admin can see all backups
        if user.is_superuser or user.role in ['super_admin', 'system_admin']:
            tenant_id = self.request.query_params.get('tenant_id')
            if tenant_id:
                return TenantBackup.objects.filter(tenant_id=tenant_id)
            return TenantBackup.objects.all()
        
        return TenantBackup.objects.none()
    
    def get_permissions(self):
        if self.action in ['create', 'destroy']:
            # Only global admins can create/delete backups
            return [IsSystemAdmin()]
        return super().get_permissions()
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore from a backup."""
        backup = self.get_object()
        
        # TODO: Implement restore logic
        # This would involve:
        # 1. Validating backup integrity
        # 2. Taking a pre-restore backup
        # 3. Restoring database and files
        # 4. Verifying restore
        
        return Response({
            'detail': 'Restore initiated',
            'backup_id': backup.id,
            'status': 'queued'
        })