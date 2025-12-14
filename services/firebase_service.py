
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, messaging
from typing import Dict, List, Optional
from datetime import datetime

class FirebaseService:
    def __init__(self):
        """Initialize Firebase Admin SDK with cloud-compatible credential loading"""
        
        # Check if Firebase is already initialized
        if not firebase_admin._apps:
            # Try to load credentials from environment variable (for cloud deployment)
            firebase_creds_env = os.getenv('FIREBASE_CREDENTIALS')
            
            if firebase_creds_env:
                # Cloud deployment: credentials as JSON string in environment
                print("📡 Loading Firebase credentials from environment variable...")
                try:
                    cred_dict = json.loads(firebase_creds_env)
                    cred = credentials.Certificate(cred_dict)
                    print("✅ Firebase credentials loaded from environment")
                except json.JSONDecodeError as e:
                    print(f"❌ Error parsing Firebase credentials: {e}")
                    raise
            else:
                # Local development: credentials from file
                cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
                print(f"📁 Loading Firebase credentials from file: {cred_path}")
                
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(
                        f"Firebase credentials file not found at {cred_path}. "
                        f"Please set FIREBASE_CREDENTIALS environment variable or provide the file."
                    )
                
                cred = credentials.Certificate(cred_path)
                print("✅ Firebase credentials loaded from file")
            
            # Initialize Firebase app
            firebase_admin.initialize_app(cred)
            print("✅ Firebase Admin SDK initialized")
        
        # Get Firestore client
        self.db = firestore.client()
    
    # Patient Operations
    async def create_patient(self, patient_data: Dict) -> str:
        """Create a new patient record"""
        patient_data['created_at'] = datetime.utcnow()
        patient_data['updated_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('patients').document()
        doc_ref.set(patient_data)
        return doc_ref.id
    
    async def get_patient(self, patient_id: str) -> Optional[Dict]:
        """Get patient by ID"""
        doc = self.db.collection('patients').document(patient_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    async def update_patient(self, patient_id: str, update_data: Dict) -> bool:
        """Update patient record"""
        update_data['updated_at'] = datetime.utcnow()
        self.db.collection('patients').document(patient_id).update(update_data)
        return True
    
    async def get_patient_visits(self, patient_id: str, limit: int = 10) -> List[Dict]:
        """Get patient visit history"""
        visits = (
            self.db.collection('visits')
            .where('patient_id', '==', patient_id)
            .order_by('visit_date', direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        
        return [{'id': v.id, **v.to_dict()} for v in visits]
    
    # Visit Operations
    async def create_visit(self, visit_data: Dict) -> str:
        """Create a new visit record"""
        visit_data['visit_date'] = datetime.utcnow()
        visit_data['status'] = 'active'
        visit_data['created_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('visits').document()
        doc_ref.set(visit_data)
        return doc_ref.id
    
    async def get_visit(self, visit_id: str) -> Optional[Dict]:
        """Get visit by ID"""
        doc = self.db.collection('visits').document(visit_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    async def update_visit(self, visit_id: str, update_data: Dict) -> bool:
        """Update visit record"""
        update_data['updated_at'] = datetime.utcnow()
        self.db.collection('visits').document(visit_id).update(update_data)
        return True
    
    # Triage Operations
    async def save_triage_result(self, triage_data: Dict) -> str:
        """Save triage assessment result"""
        triage_data['created_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('triage_results').document()
        doc_ref.set(triage_data)
        return doc_ref.id
    
    # Queue Operations
    async def add_to_queue(self, queue_data: Dict) -> str:
        """Add patient to triage queue"""
        queue_data['checked_in_at'] = datetime.utcnow()
        queue_data['status'] = 'waiting'
        
        doc_ref = self.db.collection('queue').document()
        doc_ref.set(queue_data)
        return doc_ref.id
    
    async def get_queue(self) -> List[Dict]:
        """Get current queue ordered by priority"""
        queue = (
            self.db.collection('queue')
            .where('status', '==', 'waiting')
            .order_by('priority')
            .order_by('checked_in_at')
            .stream()
        )
        
        return [{'id': q.id, **q.to_dict()} for q in queue]
    
    async def update_queue_entry(self, queue_id: str, update_data: Dict) -> bool:
        """Update queue entry"""
        self.db.collection('queue').document(queue_id).update(update_data)
        return True
    
    async def remove_from_queue(self, queue_id: str) -> bool:
        """Remove patient from queue"""
        self.db.collection('queue').document(queue_id).delete()
        return True
    
    # Alert Operations
    async def create_alert(self, alert_data: Dict) -> str:
        """Create a new alert"""
        alert_data['created_at'] = datetime.utcnow()
        alert_data['acknowledged'] = False
        
        doc_ref = self.db.collection('alerts').document()
        doc_ref.set(alert_data)
        return doc_ref.id
    
    async def get_active_alerts(self) -> List[Dict]:
        """Get unacknowledged alerts"""
        alerts = (
            self.db.collection('alerts')
            .where('acknowledged', '==', False)
            .order_by('created_at', direction=firestore.Query.DESCENDING)
            .stream()
        )
        
        return [{'id': a.id, **a.to_dict()} for a in alerts]
    
    async def acknowledge_alert(self, alert_id: str, doctor_id: str) -> bool:
        """Mark alert as acknowledged"""
        self.db.collection('alerts').document(alert_id).update({
            'acknowledged': True,
            'acknowledged_by': doctor_id,
            'acknowledged_at': datetime.utcnow()
        })
        return True
    
    # Doctor Operations
    async def get_doctor(self, doctor_id: str) -> Optional[Dict]:
        """Get doctor by ID"""
        doc = self.db.collection('doctors').document(doctor_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    async def get_doctor_by_email(self, email: str) -> Optional[Dict]:
        """Get doctor by email"""
        doctors = (
            self.db.collection('doctors')
            .where('email', '==', email)
            .limit(1)
            .stream()
        )
        
        for doc in doctors:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        
        return None
    
    async def save_doctor_notes(self, notes_data: Dict) -> str:
        """Save doctor's consultation notes"""
        notes_data['created_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('doctor_notes').document()
        doc_ref.set(notes_data)
        return doc_ref.id
    
    # Firebase Cloud Messaging (FCM)
    async def send_notification(self, token: str, title: str, body: str, data: Dict = None) -> bool:
        """Send push notification via FCM"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=token
            )
            
            response = messaging.send(message)
            print(f"✅ Notification sent: {response}")
            return True
        except Exception as e:
            print(f"❌ Error sending notification: {e}")
            return False
    
    async def send_notification_to_topic(self, topic: str, title: str, body: str, data: Dict = None) -> bool:
        """Send notification to a topic (e.g., all doctors)"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                topic=topic
            )
            
            response = messaging.send(message)
            print(f"✅ Topic notification sent: {response}")
            return True
        except Exception as e:
            print(f"❌ Error sending topic notification: {e}")
            return False

# Singleton instance
firebase_service = FirebaseService()