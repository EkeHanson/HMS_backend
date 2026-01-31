# tenants_setup.py
# Run inside Django shell: python manage.py shell < tenants_setup.py

from django.utils import timezone

from tenants.models import Tenant, TenantDomain, SubscriptionPlan, FacilityType
from core.models import Country, State, LGA

# Step 0: Get or create Country for the public tenant
country, _ = Country.objects.get_or_create(id=1, defaults={'name': 'Nigeria', 'code': 'NG', 'phone_code': '+234', 'currency': 'NGN', 'timezone': 'Africa/Lagos'})

# Get or create State for the public tenant
try:
    state = State.objects.first()
    if not state:
        state = State.objects.create(name='Lagos', code='LAG', country=country)
except State.DoesNotExist:
    state = State.objects.create(name='Lagos', code='LAG', country=country)

# Get or create LGA for the public tenant
try:
    lga = LGA.objects.first()
    if not lga:
        lga = LGA.objects.create(name=' Ikeja', state=state)
except LGA.DoesNotExist:
    lga = LGA.objects.create(name=' Ikeja', state=state)

print(f"Country: {country.name}")
print(f"State: {state.name}")
print(f"LGA: {lga.name}")

# Step 1: Get or create a valid FacilityType for the public tenant
facility_type, _ = FacilityType.objects.get_or_create(
    name="Hospital",
    defaults={'description': 'General Hospital'}
)
print(f"FacilityType: {facility_type.name}")

# Step 2: Get or create a SubscriptionPlan for the public tenant
# Create a free "Public" plan for the public tenant
subscription_plan, created = SubscriptionPlan.objects.get_or_create(
    code='PUBLIC_FREE',
    defaults={
        'name': 'Public Free Plan',
        'description': 'Free plan for public/system tenant',
        'price_monthly': 0,
        'price_quarterly': 0,
        'price_yearly': 0,
        'currency': 'NGN',
        'max_users': 10,
        'max_patients': 100,
        'max_storage_gb': 1,
        'max_api_calls_per_day': 1000,
        'trial_period_days': 0,
        'is_trial_available': False,
        'is_default': True,
    }
)
if created:
    print(f"Created SubscriptionPlan: {subscription_plan.name}")
else:
    print(f"SubscriptionPlan already exists: {subscription_plan.name}")

# Step 3: Create the public tenant
# For public tenant, we use schema_name='public'
public_tenant, created = Tenant.objects.get_or_create(
    schema_name='public',
    defaults={
        'name': 'Public Tenant',
        'code': 'PUBLIC',
        'email': 'public@localhost',
        'phone': '+1234567890',
        'phone2': '',
        'address': 'System Address',
        'city': 'System City',
        'state': state,
        'lga': lga,
        'country': country,
        'facility_type': facility_type,
        'registration_number': 'SYS-001',
        'tax_id': '',
        'website': '',
        'subscription_plan': subscription_plan,
        'subscription_status': Tenant.SubscriptionStatus.TRIAL,
        'subscription_start_date': timezone.now().date(),
        'subscription_end_date': None,
        'monthly_fee': 0,
        'payment_method': '',
        'billing_email': '',
        'nhis_accreditation': Tenant.NHISAccreditation.NOT_APPLIED,
        'nhis_provider_id': '',
        'bed_capacity': 0,
        'established_date': None,
        'operating_hours': {},
        'emergency_services': False,
        'config': {},
        'features': {},
        'notes': 'System public tenant',
    }
)
if created:
    print(f"Created public tenant: {public_tenant.name}")
else:
    print(f"Public tenant already exists: {public_tenant.name}")

# Step 4: Create the domain for the public tenant
domain, domain_created = TenantDomain.objects.get_or_create(
    domain='localhost',
    tenant=public_tenant,
    defaults={'is_primary': True}
)
if domain_created:
    print(f"Created domain: {domain.domain} for tenant {public_tenant.name}")
else:
    print(f"Domain already exists: {domain.domain}")

print("\nSetup complete!")
print(f"Public tenant schema: {public_tenant.schema_name}")
print(f"Public tenant domain: {domain.domain}")
