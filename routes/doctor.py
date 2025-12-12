from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict
from models.triage import DoctorNote
from services.firebase_service import firebase_service
from services.queue_manager import queue_manager
from services.notification_service import notification_service
from utils.security import get_current_user, require_doctor

router = APIRouter(prefix="/doctor", tags=["Doctor"])

@router.get("/queue")
async def get_queue(current_user: dict = Depends(require_doctor)):
    """Get current triage queue"""
    
    queue_stats = await queue_manager.get_queue_statistics()
    return queue_stats

@router.post("/call-patient/{visit_id}")
async def call_patient(visit_id: str, current_user: dict = Depends(require_doctor)):
    """Call patient from queue"""
    
    result = await queue_manager.call_patient(visit_id, current_user['id'])
    
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])
    
    return result

@router.post("/complete-visit/{visit_id}")
async def complete_visit(visit_id: str, current_user: dict = Depends(require_doctor)):
    """Mark visit as completed"""
    
    result = await queue_manager.complete_visit(visit_id)
    
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])
    
    return {"message": "Visit completed successfully"}

@router.post("/save-notes")
async def save_consultation_notes(note: DoctorNote, current_user: dict = Depends(require_doctor)):
    """Save doctor's consultation notes"""
    
    note_data = note.model_dump()
    note_data['doctor_id'] = current_user['id']
    note_data['doctor_name'] = current_user['name']
    
    note_id = await firebase_service.save_doctor_note(note_data)
    
    # Update visit status
    await firebase_service.update_visit(note.visit_id, {
        'status': 'completed',
        'doctor_note_id': note_id
    })
    
    # Remove from queue
    await queue_manager.complete_visit(note.visit_id)
    
    return {
        "message": "Notes saved successfully",
        "note_id": note_id
    }

@router.get("/notes/{visit_id}")
async def get_consultation_notes(visit_id: str, current_user: dict = Depends(require_doctor)):
    """Get consultation notes for a visit"""
    
    notes = await firebase_service.get_visit_notes(visit_id)
    
    if not notes:
        raise HTTPException(status_code=404, detail="Notes not found")
    
    return notes

@router.get("/alerts")
async def get_active_alerts(current_user: dict = Depends(require_doctor)):
    """Get all active alerts"""
    
    alerts = await notification_service.get_active_alerts()
    return alerts

@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(require_doctor)):
    """Acknowledge an alert"""
    
    success = await notification_service.acknowledge_alert(alert_id, current_user['id'])
    
    if success:
        return {"message": "Alert acknowledged"}
    else:
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")

@router.get("/patient/{patient_id}")
async def get_patient_details(patient_id: str, current_user: dict = Depends(require_doctor)):
    """Get complete patient details including history"""
    
    patient = await firebase_service.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    visits = await firebase_service.get_patient_visits(patient_id)
    
    return {
        "patient": patient,
        "visits": visits,
        "visit_count": len(visits)
    }

@router.get("/statistics")
async def get_doctor_statistics(current_user: dict = Depends(require_doctor)):
    """Get doctor dashboard statistics"""
    
    queue_stats = await queue_manager.get_queue_statistics()
    alerts = await notification_service.get_active_alerts()
    
    # Check for long wait patients
    long_wait = await queue_manager.check_long_wait_patients()
    
    return {
        "queue": queue_stats,
        "active_alerts": len(alerts),
        "long_wait_patients": len(long_wait),
        "critical_patients": queue_stats['critical_count']
    }