Great! Now that you have the tenant details, here's how to login as the tenant and start creating resources:

## **Step 1: Create Tenant Admin User First**

Since you don't have a tenant user yet, you need to create one first. You have two options:

### **Option A: Create Admin User via Django Shell (Recommended)**

```bash
python manage.py shell
```

```python
from tenants.models import Tenant, TenantUser
from django.db import connection

# 1. Get your tenant
tenant = Tenant.objects.get(code='LAG5268')  # or use id=1

# 2. Switch to tenant schema
connection.set_schema(tenant.schema_name)

# 3. Create tenant admin user
admin_user = TenantUser.objects.create(
    tenant=tenant,
    username='admin_lagos',
    email='admin@lagosgeneralhospital.com',
    first_name='Hospital',
    last_name='Admin',
    phone='+2348012345679',
    role='admin',
    employee_id='LGH001',
    is_staff=True,
    is_active=True
)
admin_user.set_password('Hospital@123')
admin_user.save()

print(f"Created tenant admin:")
print(f"Username: {admin_user.username}")
print(f"Password: Hospital@123")
print(f"Email: {admin_user.email}")
print(f"Role: {admin_user.role}")

# 4. Switch back to public schema
connection.set_schema('public')
```

### **Option B: Use the API Endpoint**

First, let me create a simple API endpoint for creating tenant users. Add this to **apps/tenants/views.py**:

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db import connection

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_tenant_admin(request, tenant_id):
    """Create admin user for a tenant."""
    try:
        from tenants.models import Tenant, TenantUser
        
        # Get tenant
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Switch to tenant schema
        connection.set_schema(tenant.schema_name)
        
        # Create admin user
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
        
        # Switch back to public schema
        connection.set_schema('public')
        
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
        connection.set_schema('public')
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

Add to **apps/tenants/urls.py**:
```python
from django.urls import path
from .views import create_tenant_admin

urlpatterns = [
    # ... existing URLs ...
    path('tenants/<int:tenant_id>/create-admin/', create_tenant_admin, name='create-tenant-admin'),
]
```

Then use it:
```bash
curl -X POST http://localhost:9090/api/v1/tenants/tenants/1/create-admin/ \
  -H "Authorization: Bearer <your-global-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin_lagos",
    "email": "admin@lagosgeneralhospital.com",
    "password": "Hospital@123",
    "first_name": "Hospital",
    "last_name": "Admin",
    "phone": "+2348012345679",
    "employee_id": "LGH001"
  }'
```

## **Step 2: Login as Tenant User**

Now you can login using the tenant user credentials:

### **Using the API:**

```bash
# Login as tenant user
curl -X POST http://localhost:9090/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin_lagos",
    "password": "Hospital@123"
  }'
```

**Response will include:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "admin_lagos",
    "email": "admin@lagosgeneralhospital.com",
    "role": "admin",
    "tenant": {
      "id": 1,
      "name": "Lagos General Hospital",
      "code": "LAG5268"
    }
  }
}
```

### **Important:** The system should automatically detect the tenant from the user's credentials and switch to the correct schema.

## **Step 3: Start Creating Resources as Tenant Admin**

Once logged in as tenant admin, you can create:

### **1. Create Departments**

```bash
curl -X POST http://localhost:9090/api/v1/tenants/departments/ \
  -H "Authorization: Bearer <tenant-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Outpatient Department",
    "code": "OPD",
    "description": "General outpatient consultations",
    "phone": "+2348012345678",
    "email": "opd@lagosgeneralhospital.com",
    "location": "Ground Floor, Main Building",
    "is_clinical": true
  }'
```

### **2. Create Other Staff Users**

```bash
# Create a doctor
curl -X POST http://localhost:9090/api/v1/tenants/users/ \
  -H "Authorization: Bearer <tenant-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "dr.johnson",
    "email": "johnson@lagosgeneralhospital.com",
    "password": "Doctor@123",
    "first_name": "John",
    "last_name": "Johnson",
    "phone": "+2348023456789",
    "role": "doctor",
    "employee_id": "LGH002",
    "department": 1,
    "designation": "Consultant Physician",
    "mdcn_number": "MDCN/12345"
  }'

# Create a nurse
curl -X POST http://localhost:9090/api/v1/tenants/users/ \
  -H "Authorization: Bearer <tenant-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nurse.mary",
    "email": "mary@lagosgeneralhospital.com",
    "password": "Nurse@123",
    "first_name": "Mary",
    "last_name": "James",
    "phone": "+2348034567890",
    "role": "nurse",
    "employee_id": "LGH003",
    "department": 1
  }'
```

### **3. Create Patients**

```bash
curl -X POST http://localhost:9090/api/v1/patients/patients/ \
  -H "Authorization: Bearer <tenant-admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Chinwe",
    "last_name": "Okonkwo",
    "date_of_birth": "1985-06-15",
    "gender": "female",
    "phone": "+2348045678901",
    "address": "25 Adeola Street, Victoria Island",
    "city": "Lagos",
    "state": 3,
    "blood_group": "O+",
    "genotype": "AA",
    "marital_status": "married",
    "occupation": "Banker",
    "religion": "Christian",
    "ethnicity": "Igbo"
  }'
```

## **Step 4: Test Complete Workflow**

Here's a complete testing script:

**test_tenant_workflow.py:**
```python
import requests
import json
import time

BASE_URL = "http://localhost:9090"

def test_tenant_workflow():
    print("=== Testing Tenant Workflow ===\n")
    
    # 1. Global admin login
    print("1. Logging in as global admin...")
    login_data = {
        "username": "admin",
        "password": "Admin@123456"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login/", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
    
    global_token = response.json()["access"]
    print("Global admin token obtained\n")
    
    # 2. Create tenant admin (if not exists)
    print("2. Creating tenant admin user...")
    tenant_admin_data = {
        "username": "admin_lagos",
        "email": "admin@lagosgeneralhospital.com",
        "password": "Hospital@123",
        "first_name": "Hospital",
        "last_name": "Admin",
        "phone": "+2348012345679",
        "employee_id": "LGH001"
    }
    
    headers = {"Authorization": f"Bearer {global_token}"}
    response = requests.post(
        f"{BASE_URL}/api/v1/tenants/tenants/1/create-admin/",
        json=tenant_admin_data,
        headers=headers
    )
    
    if response.status_code == 201:
        print(f"Tenant admin created: {response.json()}\n")
    elif "already exists" in response.text:
        print("Tenant admin already exists\n")
    else:
        print(f"Failed to create tenant admin: {response.text}\n")
        return
    
    # 3. Login as tenant admin
    print("3. Logging in as tenant admin...")
    tenant_login_data = {
        "username": "admin_lagos",
        "password": "Hospital@123"
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/auth/login/", json=tenant_login_data)
    if response.status_code != 200:
        print(f"Tenant login failed: {response.text}")
        return
    
    tenant_token = response.json()["access"]
    user_info = response.json()["user"]
    print(f"Tenant admin logged in: {user_info['username']}\n")
    
    tenant_headers = {"Authorization": f"Bearer {tenant_token}"}
    
    # 4. Create department
    print("4. Creating department...")
    department_data = {
        "name": "Outpatient Department",
        "code": "OPD",
        "description": "General outpatient consultations",
        "phone": "+2348012345678",
        "email": "opd@lagosgeneralhospital.com",
        "location": "Ground Floor, Main Building",
        "is_clinical": True
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/tenants/departments/",
        json=department_data,
        headers=tenant_headers
    )
    
    if response.status_code == 201:
        department_id = response.json()["id"]
        print(f"Department created with ID: {department_id}\n")
    else:
        print(f"Failed to create department: {response.text}\n")
        return
    
    # 5. Create doctor
    print("5. Creating doctor...")
    doctor_data = {
        "username": "dr.johnson",
        "email": "johnson@lagosgeneralhospital.com",
        "password": "Doctor@123",
        "first_name": "John",
        "last_name": "Johnson",
        "phone": "+2348023456789",
        "role": "doctor",
        "employee_id": "LGH002",
        "department": department_id,
        "designation": "Consultant Physician",
        "mdcn_number": "MDCN/12345"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/tenants/users/",
        json=doctor_data,
        headers=tenant_headers
    )
    
    if response.status_code == 201:
        print(f"Doctor created: {response.json()['username']}\n")
    else:
        print(f"Failed to create doctor: {response.text}\n")
    
    # 6. Create patient
    print("6. Creating patient...")
    patient_data = {
        "first_name": "Chinwe",
        "last_name": "Okonkwo",
        "date_of_birth": "1985-06-15",
        "gender": "female",
        "phone": "+2348045678901",
        "address": "25 Adeola Street, Victoria Island",
        "city": "Lagos",
        "state": 3,
        "blood_group": "O+",
        "genotype": "AA",
        "marital_status": "married",
        "occupation": "Banker",
        "religion": "Christian",
        "ethnicity": "Igbo"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/patients/patients/",
        json=patient_data,
        headers=tenant_headers
    )
    
    if response.status_code == 201:
        patient_id = response.json()["id"]
        hospital_number = response.json()["hospital_number"]
        print(f"Patient created: {hospital_number} (ID: {patient_id})\n")
    else:
        print(f"Failed to create patient: {response.text}\n")
    
    # 7. List all patients
    print("7. Listing all patients...")
    response = requests.get(
        f"{BASE_URL}/api/v1/patients/patients/",
        headers=tenant_headers
    )
    
    if response.status_code == 200:
        patients = response.json()
        print(f"Total patients: {patients['count']}")
        for patient in patients['results']:
            print(f"  - {patient['first_name']} {patient['last_name']} ({patient['hospital_number']})")
    else:
        print(f"Failed to list patients: {response.text}")
    
    print("\n=== Workflow Test Complete ===")

if __name__ == "__main__":
    test_tenant_workflow()
```

## **Step 5: Quick Setup Using Django Admin**

If you want to set things up quickly via Django Admin:

1. **Login to Django Admin:** `http://localhost:9090/admin/`
2. **Switch to tenant context:**
   - Unfortunately, Django admin doesn't automatically switch schemas
   - You need to access tenant-specific data through API or custom admin

## **Step 6: Create Custom Tenant Admin Interface**

Create **apps/tenants/tenant_admin.py**:

```python
from django.contrib import admin
from django.db import connection
from django.shortcuts import redirect
from django.urls import path
from django.http import HttpResponse

class TenantAdminSite(admin.AdminSite):
    site_header = "Tenant Administration"
    site_title = "Tenant Admin"
    index_title = "Welcome to Tenant Administration"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('switch-tenant/<int:tenant_id>/', self.admin_view(self.switch_tenant), name='switch-tenant'),
        ]
        return custom_urls + urls
    
    def switch_tenant(self, request, tenant_id):
        """Switch to tenant schema."""
        from tenants.models import Tenant
        
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            request.session['current_tenant_id'] = tenant.id
            request.session['current_tenant_schema'] = tenant.schema_name
            request.session['current_tenant_name'] = tenant.name
            
            # Switch connection schema
            connection.set_schema(tenant.schema_name)
            
            return redirect('/tenant-admin/')
        except Tenant.DoesNotExist:
            return HttpResponse("Tenant not found", status=404)

# Register tenant admin
tenant_admin_site = TenantAdminSite(name='tenant_admin')
```

## **Step 7: Alternative Simple Approach**

If the multi-tenancy is too complex right now, you can use a simpler approach:

### **Create a management command to bootstrap tenant:**

```bash
python manage.py bootstrap_tenant --tenant-id=1
```

Create **apps/tenants/management/commands/bootstrap_tenant.py**:

```python
from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Tenant, TenantUser, Department

class Command(BaseCommand):
    help = 'Bootstrap a tenant with initial data'
    
    def add_arguments(self, parser):
        parser.add_argument('--tenant-id', type=int, required=True)
    
    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            self.stderr.write(f'Tenant with ID {tenant_id} does not exist')
            return
        
        self.stdout.write(f'Bootstrapping tenant: {tenant.name}')
        
        # Switch to tenant schema
        connection.set_schema(tenant.schema_name)
        
        # 1. Create admin user if not exists
        if not TenantUser.objects.filter(username='admin').exists():
            admin = TenantUser.objects.create(
                tenant=tenant,
                username='admin',
                email=f'admin@{tenant.domain}',
                first_name='Admin',
                last_name='User',
                phone='+2348000000000',
                role='admin',
                employee_id='ADMIN001',
                is_staff=True,
                is_active=True
            )
            admin.set_password('Admin@123')
            admin.save()
            self.stdout.write(f'  ✓ Created admin user: admin / Admin@123')
        
        # 2. Create default departments
        default_departments = [
            {'name': 'Administration', 'code': 'ADMIN', 'is_clinical': False},
            {'name': 'Outpatient Department', 'code': 'OPD', 'is_clinical': True},
            {'name': 'Pharmacy', 'code': 'PHARM', 'is_clinical': False},
            {'name': 'Laboratory', 'code': 'LAB', 'is_clinical': False},
        ]
        
        for dept_data in default_departments:
            dept, created = Department.objects.get_or_create(
                tenant=tenant,
                code=dept_data['code'],
                defaults=dept_data
            )
            if created:
                self.stdout.write(f'  ✓ Created department: {dept.name}')
        
        # Switch back to public schema
        connection.set_schema('public')
        
        self.stdout.write(f'\n✅ Tenant {tenant.name} bootstrapped successfully!')
        self.stdout.write(f'   Admin login: admin / Admin@123')
        self.stdout.write(f'   API access: http://{tenant.domain}:9090/api/v1/')
```

## **Immediate Next Steps:**

1. **Create tenant admin user** using the Django shell method (Option A above)
2. **Login as tenant admin** using the API
3. **Start creating resources** (departments, staff, patients)

**Quickest path to start:**
```bash
# 1. Create tenant admin
python manage.py shell
# Then run the Python code from Option A

# 2. Login via API
curl -X POST http://localhost:9090/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin_lagos","password":"Hospital@123"}'

# 3. Save the token and start creating!
```

This should get you started with your tenant operations! Let me know which step you get stuck on.