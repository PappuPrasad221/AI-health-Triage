from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class SeverityLevel(str, Enum):
    NORMAL = "normal"
    MODERATE = "moderate"
    CRITICAL = "critical"

class TriageResult(BaseModel):
    visit_id: str
    patient_id: str
    severity_score: int = Field(..., ge=0, le=100)
    severity_level: SeverityLevel
    priority: int  # 1 = highest priority
    symptoms_detected: List[str] = []
    emergency_flags: List[str] = []
    vital_abnormalities: List[str] = []
    ai_reasoning: str
    rule_based_override: bool = False
    recommendation: str
    estimated_wait_time: Optional[int] = None  # in minutes
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QueueEntry(BaseModel):
    id: str
    visit_id: str
    patient_id: str
    patient_name: str
    age: int
    severity_level: SeverityLevel
    severity_score: int
    priority: int
    chief_complaint: str
    symptoms_summary: str
    vital_signs: Dict
    emergency_flags: List[str] = []
    queue_position: int
    estimated_wait_time: int
    checked_in_at: datetime
    status: str = "waiting"  # waiting, called, in_progress, completed

class QueueUpdate(BaseModel):
    action: str  # "add", "update_severity", "call_patient", "complete"
    entry: Optional[QueueEntry] = None
    visit_id: Optional[str] = None
    new_severity: Optional[int] = None

class Alert(BaseModel):
    id: str
    type: str  # "severity_change", "vital_deterioration", "emergency_keyword", "long_wait"
    severity: str  # "low", "medium", "high", "critical"
    title: str
    message: str
    patient_id: str
    patient_name: str
    visit_id: str
    data: Dict = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

class NotificationPayload(BaseModel):
    title: str
    body: str
    data: Dict = {}
    priority: str = "high"  # "normal" or "high"
    sound: str = "default"
    badge: Optional[int] = None

class DoctorNote(BaseModel):
    visit_id: str
    doctor_id: str
    doctor_name: str
    diagnosis: str
    treatment_plan: str
    prescriptions: List[Dict] = []
    follow_up_required: bool = False
    follow_up_date: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FollowUpCreate(BaseModel):
    visit_id: str
    patient_id: str
    symptoms_update: str
    condition_change: str  # "improved", "same", "worsened"
    new_vitals: Optional[Dict] = None