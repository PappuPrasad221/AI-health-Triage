from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class BloodType(str, Enum):
    A_POS = "A+"
    A_NEG = "A-"
    B_POS = "B+"
    B_NEG = "B-"
    AB_POS = "AB+"
    AB_NEG = "AB-"
    O_POS = "O+"
    O_NEG = "O-"
    UNKNOWN = "unknown"

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: str = Field(..., pattern=r'^\+?[1-9]\d{1,14}$')
    date_of_birth: str
    gender: Gender
    blood_type: Optional[BloodType] = BloodType.UNKNOWN
    address: Optional[str] = None
    emergency_contact: Optional[str] = None
    medical_history: Optional[List[str]] = []
    allergies: Optional[List[str]] = []
    current_medications: Optional[List[str]] = []

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VitalsBase(BaseModel):
    temperature: Optional[float] = Field(None, ge=35.0, le=43.0, description="Temperature in Celsius")
    heart_rate: Optional[int] = Field(None, ge=40, le=200, description="Heart rate in BPM")
    blood_pressure_systolic: Optional[int] = Field(None, ge=70, le=250)
    blood_pressure_diastolic: Optional[int] = Field(None, ge=40, le=150)
    respiratory_rate: Optional[int] = Field(None, ge=8, le=40, description="Breaths per minute")
    oxygen_saturation: Optional[float] = Field(None, ge=70.0, le=100.0, description="SpO2 percentage")
    weight: Optional[float] = Field(None, ge=0.5, le=300.0, description="Weight in kg")
    height: Optional[float] = Field(None, ge=30.0, le=250.0, description="Height in cm")

class VitalsResponse(VitalsBase):
    id: str
    patient_id: str
    visit_id: str
    recorded_at: datetime
    abnormal_flags: List[str] = []

class SymptomInput(BaseModel):
    symptom_text: str = Field(..., min_length=10, max_length=2000, description="Patient's symptom description")
    duration: Optional[str] = None
    severity_self_reported: Optional[int] = Field(None, ge=1, le=10)
    additional_notes: Optional[str] = None

class VisitCreate(BaseModel):
    patient_id: str
    symptoms: SymptomInput
    vitals: VitalsBase
    chief_complaint: str

class VisitResponse(BaseModel):
    id: str
    patient_id: str
    visit_date: datetime
    status: str  # "waiting", "in_progress", "completed"
    triage_score: Optional[int] = None
    severity_level: Optional[str] = None
    queue_position: Optional[int] = None
    assigned_doctor_id: Optional[str] = None
    consultation_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None