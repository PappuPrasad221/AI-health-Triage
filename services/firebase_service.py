import firebase_admin
from firebase_admin import credentials, firestore, messaging
from typing import Dict, List, Optional
import json
from datetime import datetime
from config import settings

class FirebaseService:
    def __init__(self):
        if not firebase_admin._apps:
            # Initialize Firebase Admin SDK
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        
        self.db = firestore.client()
        
    # ==================== PATIENT OPERATIONS ====================
    
    async def create_patient(self, patient_data: Dict) -> str:
        """Create a new patient record"""
        patient_data['created_at'] = datetime.utcnow()
        patient_data['updated_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('patients').document()
        doc_ref.set(patient_data)
        return doc_ref.id
    
    async def get_patient(self, patient_id: str) -> Optional[Dict]:
        """Retrieve patient by ID"""
        doc = self.db.collection('patients').document(patient_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    async def update_patient(self, patient_id: str, updates: Dict) -> bool:
        """Update patient information"""
        updates['updated_at'] = datetime.utcnow()
        self.db.collection('patients').document(patient_id).update(updates)
        return True
    
    # ==================== VISIT OPERATIONS ====================
    
    async def create_visit(self, visit_data: Dict) -> str:
        """Create a new visit record"""
        visit_data['visit_date'] = datetime.utcnow()
        visit_data['created_at'] = datetime.utcnow()
        visit_data['status'] = 'waiting'
        
        doc_ref = self.db.collection('visits').document()
        doc_ref.set(visit_data)
        return doc_ref.id
    
    async def get_visit(self, visit_id: str) -> Optional[Dict]:
        """Retrieve visit by ID"""
        doc = self.db.collection('visits').document(visit_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    async def update_visit(self, visit_id: str, updates: Dict) -> bool:
        """Update visit information"""
        updates['updated_at'] = datetime.utcnow()
        self.db.collection('visits').document(visit_id).update(updates)
        return True
    
    async def get_patient_visits(self, patient_id: str) -> List[Dict]:
        """Get all visits for a patient"""
        docs = self.db.collection('visits').where('patient_id', '==', patient_id).order_by('visit_date', direction=firestore.Query.DESCENDING).stream()
        visits = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            visits.append(data)
        return visits
    
    # ==================== TRIAGE OPERATIONS ====================
    
    async def save_triage_result(self, triage_data: Dict) -> str:
        """Save triage assessment result"""
        triage_data['created_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('triage_results').document()
        doc_ref.set(triage_data)
        return doc_ref.id
    
    # ==================== QUEUE OPERATIONS ====================
    
    async def add_to_queue(self, queue_entry: Dict) -> str:
        """Add patient to the triage queue"""
        queue_entry['checked_in_at'] = datetime.utcnow()
        queue_entry['status'] = 'waiting'
        
        doc_ref = self.db.collection('queue').document()
        doc_ref.set(queue_entry)
        return doc_ref.id
    
    async def get_queue(self) -> List[Dict]:
        """Get current queue sorted by priority"""
        docs = self.db.collection('queue').where('status', '==', 'waiting').order_by('priority').order_by('checked_in_at').stream()
        
        queue = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            queue.append(data)
        return queue
    
    async def update_queue_entry(self, entry_id: str, updates: Dict) -> bool:
        """Update a queue entry"""
        self.db.collection('queue').document(entry_id).update(updates)
        return True
    
    async def remove_from_queue(self, entry_id: str) -> bool:
        """Remove entry from queue"""
        self.db.collection('queue').document(entry_id).delete()
        return True
    
    # ==================== ALERT OPERATIONS ====================
    
    async def create_alert(self, alert_data: Dict) -> str:
        """Create a new alert"""
        alert_data['created_at'] = datetime.utcnow()
        alert_data['acknowledged'] = False
        
        doc_ref = self.db.collection('alerts').document()
        doc_ref.set(alert_data)
        return doc_ref.id
    
    async def get_active_alerts(self) -> List[Dict]:
        """Get all unacknowledged alerts"""
        docs = self.db.collection('alerts').where('acknowledged', '==', False).order_by('created_at', direction=firestore.Query.DESCENDING).stream()
        
        alerts = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            alerts.append(data)
        return alerts
    
    async def acknowledge_alert(self, alert_id: str, doctor_id: str) -> bool:
        """Mark alert as acknowledged"""
        self.db.collection('alerts').document(alert_id).update({
            'acknowledged': True,
            'acknowledged_by': doctor_id,
            'acknowledged_at': datetime.utcnow()
        })
        return True
    
    # ==================== DOCTOR NOTES ====================
    
    async def save_doctor_note(self, note_data: Dict) -> str:
        """Save doctor's consultation notes"""
        note_data['created_at'] = datetime.utcnow()
        
        doc_ref = self.db.collection('doctor_notes').document()
        doc_ref.set(note_data)
        return doc_ref.id
    
    async def get_visit_notes(self, visit_id: str) -> Optional[Dict]:
        """Get doctor notes for a visit"""
        docs = self.db.collection('doctor_notes').where('visit_id', '==', visit_id).limit(1).stream()
        
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            return data
        return None
    
    # ==================== PUSH NOTIFICATIONS ====================
    
    async def send_notification(self, device_token: str, notification_data: Dict) -> bool:
        """Send push notification via Firebase Cloud Messaging"""
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=notification_data.get('title', 'Alert'),
                    body=notification_data.get('body', '')
                ),
                data=notification_data.get('data', {}),
                token=device_token,
                android=messaging.AndroidConfig(
                    priority='high',
                    notification=messaging.AndroidNotification(
                        sound='default',
                        priority='high'
                    )
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound='default',
                            badge=notification_data.get('badge', 1)
                        )
                    )
                )
            )
            
            response = messaging.send(message)
            print(f"Successfully sent message: {response}")
            return True
        except Exception as e:
            print(f"Error sending notification: {e}")
            return False
    
    async def send_multicast_notification(self, device_tokens: List[str], notification_data: Dict) -> Dict:
        """Send notification to multiple devices"""
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=notification_data.get('title', 'Alert'),
                    body=notification_data.get('body', '')
                ),
                data=notification_data.get('data', {}),
                tokens=device_tokens
            )
            
            response = messaging.send_multicast(message)
            return {
                'success_count': response.success_count,
                'failure_count': response.failure_count
            }
        except Exception as e:
            print(f"Error sending multicast notification: {e}")
            return {'success_count': 0, 'failure_count': len(device_tokens)}
    
    # ==================== USER/DOCTOR OPERATIONS ====================
    
    async def get_doctor_devices(self, doctor_id: str) -> List[str]:
        """Get all device tokens for a doctor"""
        doc = self.db.collection('doctors').document(doctor_id).get()
        if doc.exists:
            data = doc.to_dict()
            return data.get('device_tokens', [])
        return []
    
    async def register_device_token(self, user_id: str, device_token: str, user_type: str = 'doctor') -> bool:
        """Register device token for push notifications"""
        collection = 'doctors' if user_type == 'doctor' else 'patients'
        doc_ref = self.db.collection(collection).document(user_id)
        
        doc = doc_ref.get()
        if doc.exists:
            tokens = doc.to_dict().get('device_tokens', [])
            if device_token not in tokens:
                tokens.append(device_token)
                doc_ref.update({'device_tokens': tokens})
        else:
            doc_ref.set({'device_tokens': [device_token]})
        
        return True

# Singleton instance
firebase_service = FirebaseService()