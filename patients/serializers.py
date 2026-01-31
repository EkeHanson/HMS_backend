from rest_framework import serializers
from django.utils import timezone

from .models import (
    Patient, PatientVisit, PatientDocument,
    PatientAllergy, PatientMedication, Appointment
)


class PatientSerializer(serializers.ModelSerializer):
    """Serializer for Patient model."""
    full_name = serializers.SerializerMethodField()
    age_display = serializers.SerializerMethodField()
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['hospital_number', 'registration_date', 'age']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_age_display(self, obj):
        return obj.get_age_display()


class PatientVisitSerializer(serializers.ModelSerializer):
    """Serializer for PatientVisit model."""
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.get_full_name', read_only=True)
    nurse_name = serializers.CharField(source='nurse.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    waiting_time = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientVisit
        fields = '__all__'
        read_only_fields = ['visit_number', 'checkin_time']
    
    def get_waiting_time(self, obj):
        waiting = obj.get_waiting_time()
        if waiting:
            minutes = waiting.total_seconds() / 60
            return f"{int(minutes)} minutes"
        return None


class PatientDocumentSerializer(serializers.ModelSerializer):
    """Serializer for PatientDocument model."""
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True)
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PatientDocument
        fields = '__all__'
        read_only_fields = ['file_name', 'file_size', 'file_type', 'upload_date']
    
    def get_file_size_display(self, obj):
        if obj.file_size:
            if obj.file_size < 1024:
                return f"{obj.file_size} B"
            elif obj.file_size < 1024 * 1024:
                return f"{obj.file_size / 1024:.1f} KB"
            else:
                return f"{obj.file_size / (1024 * 1024):.1f} MB"
        return None


class PatientAllergySerializer(serializers.ModelSerializer):
    """Serializer for PatientAllergy model."""
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)
    
    class Meta:
        model = PatientAllergy
        fields = '__all__'


class PatientMedicationSerializer(serializers.ModelSerializer):
    """Serializer for PatientMedication model."""
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    prescribed_by_name = serializers.CharField(source='prescribed_by.get_full_name', read_only=True)
    
    class Meta:
        model = PatientMedication
        fields = '__all__'


class AppointmentSerializer(serializers.ModelSerializer):
    """Serializer for Appointment model."""
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.get_full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    is_past_due = serializers.SerializerMethodField()
    
    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['appointment_number']
    
    def get_is_past_due(self, obj):
        return obj.is_past_due()


class PatientSearchSerializer(serializers.Serializer):
    """Serializer for patient search."""
    hospital_number = serializers.CharField(required=False)
    nhis_number = serializers.CharField(required=False)
    nin = serializers.CharField(required=False)
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone = serializers.CharField(required=False)
    email = serializers.CharField(required=False)


class AppointmentScheduleSerializer(serializers.Serializer):
    """Serializer for scheduling appointments."""
    patient_id = serializers.IntegerField()
    doctor_id = serializers.IntegerField()
    department_id = serializers.IntegerField(required=False)
    appointment_type = serializers.CharField()
    scheduled_date = serializers.DateField()
    scheduled_time = serializers.TimeField()
    reason = serializers.CharField(required=False)
    notes = serializers.CharField(required=False)