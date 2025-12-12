from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from datetime import datetime
from models.patient import VisitCreate
from models.triage import TriageResult, FollowUpCreate
from services.firebase_service import firebase_service
from services.ai_engine import ai_engine
from services.queue_manager import queue_manager
from services.notification_service import notification_service
from utils.security import get_current_user

router = APIRouter(prefix="/triage", tags=["Triage"])

@router.post("/assess", response_model=Dict)
async def assess_patient(visit: VisitCreate, current_user: dict = Depends(get_current_user)):
    """
    Complete triage assessment workflow:
    1. Create visit record
    2. Run AI analysis
    3. Add to priority queue
    4. Send notifications if critical
    """
    
    # Step 1: Create visit record
    visit_data = {
        'patient_id': visit.patient_id,
        'chief_complaint': visit.chief_complaint,
        'symptoms': visit.symptoms.model_dump(),
        'vitals': visit.vitals.model_dump()
    }
    
    visit_id = await firebase_service.create_visit(visit_data)
    
    # Step 2: Get patient info
    patient = await firebase_service.get_patient(visit.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Step 3: Run AI triage assessment
    triage_result = ai_engine.predict_severity(
        symptom_text=visit.symptoms.symptom_text,
        vitals=visit.vitals.model_dump(exclude_none=True),
        duration=visit.symptoms.duration
    )
    
    # Step 4: Save triage result
    triage_data = {
        'visit_id': visit_id,
        'patient_id': visit.patient_id,
        **triage_result
    }
    
    triage_id = await firebase_service.save_triage_result(triage_data)
    
    # Step 5: Update visit with triage results
    await firebase_service.update_visit(visit_id, {
        'triage_score': triage_result['severity_score'],
        'severity_level': triage_result['severity_level'],
        'triage_result_id': triage_id
    })
    
    # Step 6: Calculate patient age for queue entry
    from datetime import datetime
    dob = datetime.fromisoformat(patient['date_of_birth'].replace('Z', '+00:00')) if isinstance(patient['date_of_birth'], str) else patient['date_of_birth']
    age = (datetime.utcnow() - dob).days // 365
    
    # Step 7: Add to priority queue
    queue_entry = {
        'visit_id': visit_id,
        'patient_id': visit.patient_id,
        'patient_name': f"{patient['first_name']} {patient['last_name']}",
        'age': age,
        'severity_level': triage_result['severity_level'],
        'severity_score': triage_result['severity_score'],
        'priority': triage_result['priority'],
        'chief_complaint': visit.chief_complaint,
        'symptoms_summary': visit.symptoms.symptom_text[:200],
        'vital_signs': visit.vitals.model_dump(exclude_none=True),
        'emergency_flags': triage_result['emergency_flags'],
        'queue_position': 0  # Will be calculated by queue manager
    }
    
    queue_result = await queue_manager.add_to_queue(queue_entry)
    
    # Step 8: Send notifications if critical
    if triage_result['severity_level'] == 'critical':
        await notification_service.notify_severity_change(
            patient_id=visit.patient_id,
            patient_name=queue_entry['patient_name'],
            visit_id=visit_id,
            old_severity='none',
            new_severity='critical',
            severity_score=triage_result['severity_score']
        )
    
    # Step 9: Check for vital abnormalities
    if triage_result['vital_abnormalities']:
        await notification_service.notify_vital_deterioration(
            patient_id=visit.patient_id,
            patient_name=queue_entry['patient_name'],
            visit_id=visit_id,
            abnormalities=triage_result['vital_abnormalities']
        )
    
    return {
        'visit_id': visit_id,
        'triage_result': triage_result,
        'queue_entry': queue_result,
        'message': 'Triage assessment completed successfully'
    }

@router.post("/follow-up")
async def follow_up_assessment(
    follow_up: FollowUpCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Reassess patient based on follow-up information
    """
    
    # Get original visit
    visit = await firebase_service.get_visit(follow_up.visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    original_score = visit.get('triage_score', 0)
    
    # Reassess severity
    reassessment = ai_engine.reassess_severity(
        original_score=original_score,
        follow_up_text=follow_up.symptoms_update,
        condition_change=follow_up.condition_change
    )
    
    new_score = reassessment['severity_score']
    new_severity = reassessment['severity_level']
    
    # Update visit
    await firebase_service.update_visit(follow_up.visit_id, {
        'triage_score': new_score,
        'severity_level': new_severity,
        'follow_up_note': follow_up.symptoms_update,
        'condition_change': follow_up.condition_change
    })
    
    # Update queue if severity changed
    old_severity = visit.get('severity_level', 'normal')
    
    if new_severity != old_severity or abs(new_score - original_score) > 10:
        queue_update = await queue_manager.update_severity(
            visit_id=follow_up.visit_id,
            new_severity_score=new_score,
            new_severity_level=new_severity
        )
        
        # Send notification
        patient = await firebase_service.get_patient(follow_up.patient_id)
        patient_name = f"{patient['first_name']} {patient['last_name']}"
        
        if follow_up.condition_change == 'worsened':
            await notification_service.notify_follow_up_worsening(
                patient_id=follow_up.patient_id,
                patient_name=patient_name,
                visit_id=follow_up.visit_id,
                original_score=original_score,
                new_score=new_score
            )
        elif new_severity == 'critical' and old_severity != 'critical':
            await notification_service.notify_severity_change(
                patient_id=follow_up.patient_id,
                patient_name=patient_name,
                visit_id=follow_up.visit_id,
                old_severity=old_severity,
                new_severity=new_severity,
                severity_score=new_score
            )
    
    return {
        'message': 'Follow-up assessment completed',
        'reassessment': reassessment,
        'severity_changed': new_severity != old_severity
    }

@router.get("/result/{visit_id}")
async def get_triage_result(visit_id: str, current_user: dict = Depends(get_current_user)):
    """Get triage result for a visit"""
    
    visit = await firebase_service.get_visit(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    return visit