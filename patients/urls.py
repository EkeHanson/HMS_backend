from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PatientViewSet, PatientVisitViewSet, AppointmentViewSet

router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'visits', PatientVisitViewSet, basename='visit')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]