from fastapi import APIRouter, Depends, HTTPException
from typing import List
from models.patient import PatientCreate, PatientResponse, VisitCreate, VisitResponse
from services.firebase_service import firebase_service
from utils.security import get_current_user

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post("/", response_model=PatientResponse)
async def create_patient(patient: PatientCreate, current_user: dict = Depends(get_current_user)):
    """Create a new patient record"""
    
    patient_data = patient.model_dump()
    patient_id = await firebase_service.create_patient(patient_data)
    
    created_patient = await firebase_service.get_patient(patient_id)
    return created_patient

@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Get patient by ID"""
    
    patient = await firebase_service.get_patient(patient_id)
    
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return patient

@router.put("/{patient_id}")
async def update_patient(
    patient_id: str,
    updates: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update patient information"""
    
    success = await firebase_service.update_patient(patient_id, updates)
    
    if success:
        return {"message": "Patient updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update patient")

@router.get("/{patient_id}/visits", response_model=List[VisitResponse])
async def get_patient_visits(patient_id: str, current_user: dict = Depends(get_current_user)):
    """Get all visits for a patient"""
    
    visits = await firebase_service.get_patient_visits(patient_id)
    return visits