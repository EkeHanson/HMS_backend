# SmartCare HMS - Complete Setup Guide

This guide provides step-by-step instructions to set up the SmartCare Hospital Management System with multi-tenant support using django-tenants.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Django 4.2+
- Virtual environment (recommended)

## Quick Start

### 1. Create Virtual Environment
```bash
cd C:\Users\Ekene-onwon\Desktop\Codes\HMS-front_back\BAckend
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Setup
Make sure PostgreSQL is running and create the database:
```sql
CREATE DATABASE hospital_ms;
```

Configure connection in settings or use the provided connection string in `.env`.

### 4. Run Initial Setup Script
```bash
# Start Django shell and run the setup script
python manage.py shell < tenants_setup.py
```

This will create:
- Country (Nigeria)
- State (Lagos/Abuja if not exists)
- LGA (Ikeja/Abuja Municipal if not exists)
- FacilityType (Hospital)
- SubscriptionPlan (Public Free Plan)
- Public tenant (schema: 'public')
- Domain 'localhost' for public tenant

---

## Step-by-Step Tenant Setup Process

### **Step 1: Create Superuser (Global Admin)**
```bash
python manage.py createsuperuser
```
Enter:
- Username: `admin`
- Email: `admin@smartcarehms.com`
- Password: `Admin@123456` (use a strong password)

### **Step 2: Start Django Server**
```bash
python manage.py runserver 0.0.0.0:9090
```
Visit: http://localhost:9090/admin

### **Step 3: Log in to Admin Panel**
- Login with your superuser credentials
- You'll see the Django admin interface

### **Step 4: Set Up Core Data (One-Time Setup)**

#### **4.1 Add Countries**
1. Go to `Core → Countries`
2. Click `ADD COUNTRY +`
3. Add Nigeria:
   - Name: `Nigeria`
   - Code: `NG`
   - Phone code: `+234`
   - Currency: `NGN`
   - Timezone: `Africa/Lagos`
   - Is active: ✅

#### **4.2 Add States (Nigerian States)**
1. Go to `Core → States`
2. Add Nigerian states (you can add a few key ones):
   - **Lagos State:**
     - Name: `Lagos`
     - Code: `LAG`
     - Country: `Nigeria`
   - **Abuja (FCT):**
     - Name: `Abuja`
     - Code: `ABJ`
     - Country: `Nigeria`

#### **4.3 Add LGAs (Local Government Areas)**
1. Go to `Core → Local Government Areas`
2. Add LGAs for each state:
   - **For Lagos:**
     - Ikeja, Surulere, Lagos Island, etc.
   - **For Abuja:**
     - Abuja Municipal, Bwari, etc.

#### **4.4 Add Facility Types**
1. Go to `Core → Facility Types`
2. Add common healthcare facility types:
   - General Hospital
   - Specialist Hospital
   - Primary Health Center
   - Diagnostic Center
   - Maternity Home

### **Step 5: Create Subscription Plans**
1. Go to `Tenants → Subscription plans`
2. Click `ADD SUBSCRIPTION PLAN +`
3. Create basic plans:

   **Plan 1: Basic Plan**
   - Name: `Basic Plan`
   - Code: `BASIC`
   - Price monthly: `50000.00` (₦50,000)
   - Price quarterly: `135000.00` (₦135,000 - 10% discount)
   - Price yearly: `490900.00` (₦480,000 - 20% discount)
   - Max users: `10`
   - Max patients: `1000`
   - Max storage GB: `10`
   - Is default: ✅

   **Plan 2: Pro Plan**
   - Name: `Pro Plan`
   - Code: `PRO`
   - Price monthly: `100000.00` (₦100,000)
   - Max users: `25`
   - Max patients: `5000`
   - Max storage GB: `50`

### **Step 6: Create Your First Tenant**

#### **6.1 Create Tenant Record**
1. Go to `Tenants → Tenants`
2. Click `ADD TENANT +`
3. Fill in tenant details:

   **Basic Information:**
   - Name: `Lagos General Hospital`
   - Code: `LGH` (auto-generated if blank)
   - Domain: `lagosgeneral.smartcarehms.local` (for local testing)
   - Is active: ✅

   **Contact Information:**
   - Email: `info@lagosgeneralhospital.com`
   - Phone: `+2348012345678`
   - Address: `1 Hospital Road, Ikeja`
   - City: `Ikeja`
   - State: `Lagos`
   - LGA: `Ikeja`
   - Country: `Nigeria`
   - Website: `https://lagosgeneralhospital.com`

   **Facility Details:**
   - Facility type: `General Hospital`
   - Registration number: `LGH/2023/001`
   - Bed capacity: `150`
   - Emergency services: ✅
   - Established date: `2024-01-01`

   **Subscription:**
   - Subscription plan: `Basic Plan`
   - Subscription status: `Active`
   - Subscription start date: `2024-01-01`
   - Subscription end date: `2025-01-01`
   - Monthly fee: `50000.00`

   **Save the tenant**

#### **6.2 Create Database Schema for Tenant**
Since we're using django-tenants, we need to create the schema:

```bash
python manage.py create_tenant_schema <tenant_id>
```
Replace `<tenant_id>` with the ID of the tenant you just created.

### **Step 7: Create Tenant Admin User**

#### **7.1 Create Global User for Admin Access**
1. Go to `Users → Global Users`
2. Click `ADD GLOBAL USER +`
3. Create hospital admin:
   - Username: `admin_lgh`
   - Email: `admin@lagosgeneralhospital.com`
   - Password: `Hospital@123`
   - First name: `Hospital`
   - Last name: `Admin`
   - Role: `System Administrator`
   - Phone: `+2348012345679`

### **Step 8: Test Tenant Access**

#### **8.1 Configure Hosts File (for local testing)**
Edit `C:\Windows\System32\drivers\etc\hosts` (as Administrator):
```
127.0.0.1       localhost
127.0.0.1       admin.smartcarehms.local
127.0.0.1       lagosgeneral.smartcarehms.local
```

#### **8.2 API Testing**
Use the public schema endpoints for authentication:

**Login:**
- URL: `http://localhost:9090/api/v1/auth/login/`
- Method: POST
- Body:
```json
{
    "username": "admin",
    "password": "Admin@123456"
}
```

#### **8.3 Tenant Access via Header**
For tenant-specific API access, include the `X-Tenant-ID` header:

```bash
curl -X GET http://localhost:9090/api/v1/patients/ \
  -H "X-Tenant-ID: 1" \
  -H "Authorization: Bearer <token>"
```

---

## Project Structure

```
BAckend/
├── smartcare_hms/
│   ├── settings.py          # Django settings
│   ├── urls.py              # Main URL configuration
│   ├── urls_public.py       # Public schema URLs (admin, auth, etc.)
│   └── wsgi.py
├── tenants/
│   ├── models.py            # Tenant, TenantDomain, SubscriptionPlan
│   ├── middleware.py        # HeaderTenantMiddleware
│   ├── views.py             # Tenant API views
│   └── urls.py              # Tenant URLs
├── users/
├── core/
├── patients/
├── clinical/
├── pharmacy/
├── lab/
├── billing/
└── tenants_setup.py         # Initial setup script
```

---

## URL Configuration

### Public Schema URLs (`smartcare_hms/urls_public.py`)
Accessible from the public schema (localhost, admin domain):
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('users.urls')),
    path('api/v1/core/', include('core.urls')),
    path('api/v1/tenants/', include('tenants.urls')),
]
```

### Tenant Schema URLs (`smartcare_hms/urls.py`)
Accessible from tenant-specific domains:
```python
urlpatterns = [
    path('api/v1/patients/', include('patients.urls')),
    path('api/v1/clinical/', include('clinical.urls')),
    path('api/v1/pharmacy/', include('pharmacy.urls')),
    path('api/v1/lab/', include('lab.urls')),
    path('api/v1/billing/', include('billing.urls')),
    path('api/v1/auth/', include('users.urls')),
]
```

---

## Tenant Middleware

The `HeaderTenantMiddleware` supports:
- **Public URLs**: `/admin/`, `/api/v1/auth/`, `/api/v1/core/`, `/api/v1/tenants/`
- **Header-based resolution**: Use `X-Tenant-ID` header for tenant-specific requests
- **Domain-based resolution**: Automatically resolves tenant from domain

### Settings (`smartcare_hms/settings.py`)
```python
MIDDLEWARE = [
    'django_tenants.middleware.main.TenantMainMiddleware',
    'tenants.middleware.HeaderTenantMiddleware',
    # ... other middleware
]

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.TenantDomain"
PUBLIC_SCHEMA_NAME = 'public'
PUBLIC_SCHEMA_URLCONF = 'smartcare_hms.urls_public'
TENANT_SCHEMA_URLCONF = 'smartcare_hms.urls'
```

---

## Troubleshooting

### Error: `ModuleNotFoundError: No module named 'smartcare_hms.urls_public'`
**Solution**: The `urls_public.py` file must exist in `smartcare_hms/` directory. Run:
```bash
python manage.py shell < tenants_setup.py
```

### Error: `AttributeError: 'NoneType' object has no attribute 'schema_name'`
**Solution**: Ensure the public tenant is created in the database:
```bash
python manage.py shell
>>> from tenants.models import Tenant, TenantDomain
>>> Tenant.objects.filter(schema_name='public').exists()
```

### Error: `HeaderTenantMiddleware.get_tenant() takes 2 positional arguments but 3 were given`
**Solution**: The middleware has been updated to use `process_request` instead of `get_tenant`. Ensure you're using the latest version of `tenants/middleware.py`.

### Database Connection Issues
**Solution**: Verify PostgreSQL is running and the database exists:
```sql
CREATE DATABASE hospital_ms;
```

### Migrations Not Running on Tenant Schemas
**Solution**: Run migrations with schema support:
```bash
python manage.py migrate_schemas --shared
```

---

## Development Tips

1. **Use SQLite for development** (optional):
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': BASE_DIR / 'db.sqlite3',
       }
   }
   ```

2. **Enable debug mode**:
   ```python
   DEBUG = True
   ```

3. **Check tenant schema**:
   ```python
   from django.db import connection
   print(connection.schema_name)
   ```

4. **Switch between schemas**:
   ```python
   from django.db import connection
   connection.set_schema_to_public()  # Public schema
   connection.set_tenant(tenant)      # Tenant schema
   ```
