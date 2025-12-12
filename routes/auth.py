from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, EmailStr
from typing import Optional
from utils.security import hash_password, verify_password, create_access_token
from services.firebase_service import firebase_service
from datetime import timedelta

router = APIRouter(prefix="/auth", tags=["Authentication"])

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    user_type: str  # "doctor" or "patient"
    phone: Optional[str] = None
    specialization: Optional[str] = None  # For doctors
    license_number: Optional[str] = None  # For doctors

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    user_type: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class DeviceTokenRegister(BaseModel):
    device_token: str

@router.post("/register", response_model=TokenResponse)
async def register(user: UserRegister):
    """Register a new user (doctor or patient)"""
    
    # Check if user already exists
    collection = "doctors" if user.user_type == "doctor" else "patients"
    existing_users = firebase_service.db.collection(collection).where('email', '==', user.email).limit(1).stream()
    
    for _ in existing_users:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    # Hash password
    hashed_password = hash_password(user.password)
    
    # Prepare user data
    user_data = {
        'email': user.email,
        'password': hashed_password,
        'name': user.name,
        'phone': user.phone,
        'user_type': user.user_type,
        'device_tokens': []
    }
    
    if user.user_type == "doctor":
        user_data['specialization'] = user.specialization
        user_data['license_number'] = user.license_number
        user_data['verified'] = False  # Require verification
    
    # Save to Firebase
    doc_ref = firebase_service.db.collection(collection).document()
    doc_ref.set(user_data)
    user_id = doc_ref.id
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user_id,
            "email": user.email,
            "name": user.name,
            "type": user.user_type
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": user.email,
            "name": user.name,
            "type": user.user_type
        }
    }

@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user"""
    
    collection = "doctors" if credentials.user_type == "doctor" else "patients"
    
    # Find user by email
    users = firebase_service.db.collection(collection).where('email', '==', credentials.email).limit(1).stream()
    
    user_doc = None
    user_id = None
    for doc in users:
        user_doc = doc.to_dict()
        user_id = doc.id
        break
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not verify_password(credentials.password, user_doc['password']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if doctor is verified
    if credentials.user_type == "doctor" and not user_doc.get('verified', False):
        raise HTTPException(status_code=403, detail="Doctor account pending verification")
    
    # Create access token
    access_token = create_access_token(
        data={
            "sub": user_id,
            "email": user_doc['email'],
            "name": user_doc['name'],
            "type": credentials.user_type
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user_id,
            "email": user_doc['email'],
            "name": user_doc['name'],
            "type": credentials.user_type
        }
    }

@router.post("/register-device")
async def register_device_token(
    user_id: str = Body(...),
    user_type: str = Body(...),
    device_token_data: DeviceTokenRegister = Body(...)
):
    """Register device token for push notifications"""
    
    success = await firebase_service.register_device_token(
        user_id,
        device_token_data.device_token,
        user_type
    )
    
    if success:
        return {"message": "Device token registered successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to register device token")