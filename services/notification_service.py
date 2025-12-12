from typing import Dict, List
from datetime import datetime
from services.firebase_service import firebase_service
from models.triage import Alert, NotificationPayload
import uuid

class NotificationService:
    def __init__(self):
        self.alert_types = {
            'severity_change': {
                'title': 'Patient Severity Changed',
                'priority': 'high',
                'sound': 'emergency_alert.mp3'
            },
            'new_critical': {
                'title': 'New Critical Patient',
                'priority': 'high',
                'sound': 'emergency_alert.mp3'
            },
            'vital_deterioration': {
                'title': 'Patient Vitals Deteriorating',
                'priority': 'high',
                'sound': 'warning.mp3'
            },
            'long_wait': {
                'title': 'Patient Waiting Too Long',
                'priority': 'normal',
                'sound': 'default'
            },
            'follow_up_worsening': {
                'title': 'Follow-up Shows Worsening',
                'priority': 'high',
                'sound': 'warning.mp3'
            }
        }
    
    async def create_alert(
        self,
        alert_type: str,
        patient_id: str,
        patient_name: str,
        visit_id: str,
        message: str,
        data: Dict = {}
    ) -> str:
        """Create an alert in the system"""
        
        alert_config = self.alert_types.get(alert_type, {
            'title': 'System Alert',
            'priority': 'normal',
            'sound': 'default'
        })
        
        # Determine severity
        if alert_config['priority'] == 'high':
            severity = 'high'
        else:
            severity = 'medium'
        
        if 'critical' in alert_type.lower() or 'emergency' in message.lower():
            severity = 'critical'
        
        alert_data = {
            'type': alert_type,
            'severity': severity,
            'title': alert_config['title'],
            'message': message,
            'patient_id': patient_id,
            'patient_name': patient_name,
            'visit_id': visit_id,
            'data': data
        }
        
        alert_id = await firebase_service.create_alert(alert_data)
        return alert_id
    
    async def send_notification_to_doctors(
        self,
        alert_type: str,
        message: str,
        data: Dict = {},
        doctor_ids: List[str] = None
    ) -> Dict:
        """Send push notifications to doctors"""
        
        alert_config = self.alert_types.get(alert_type, {
            'title': 'System Alert',
            'priority': 'high',
            'sound': 'default'
        })
        
        notification_data = {
            'title': alert_config['title'],
            'body': message,
            'data': {
                'type': alert_type,
                'timestamp': datetime.utcnow().isoformat(),
                **data
            },
            'priority': alert_config['priority'],
            'sound': alert_config['sound']
        }
        
        # If specific doctors not specified, send to all available doctors
        if not doctor_ids:
            doctor_ids = await self.get_all_doctor_ids()
        
        # Get device tokens for all doctors
        all_tokens = []
        for doctor_id in doctor_ids:
            tokens = await firebase_service.get_doctor_devices(doctor_id)
            all_tokens.extend(tokens)
        
        if not all_tokens:
            return {'success': False, 'message': 'No device tokens found'}
        
        # Send multicast notification
        result = await firebase_service.send_multicast_notification(all_tokens, notification_data)
        
        return {
            'success': True,
            'sent_to': len(all_tokens),
            'success_count': result['success_count'],
            'failure_count': result['failure_count']
        }
    
    async def notify_severity_change(
        self,
        patient_id: str,
        patient_name: str,
        visit_id: str,
        old_severity: str,
        new_severity: str,
        severity_score: int
    ):
        """Notify doctors when patient severity changes"""
        
        if new_severity == 'critical':
            alert_type = 'new_critical'
            message = f"🚨 {patient_name} is now CRITICAL (Score: {severity_score}). Immediate attention required!"
        else:
            alert_type = 'severity_change'
            message = f"⚠️ {patient_name}'s severity changed from {old_severity.upper()} to {new_severity.upper()} (Score: {severity_score})"
        
        # Create alert
        await self.create_alert(
            alert_type=alert_type,
            patient_id=patient_id,
            patient_name=patient_name,
            visit_id=visit_id,
            message=message,
            data={
                'old_severity': old_severity,
                'new_severity': new_severity,
                'severity_score': severity_score
            }
        )
        
        # Send push notification
        await self.send_notification_to_doctors(
            alert_type=alert_type,
            message=message,
            data={
                'patient_id': patient_id,
                'visit_id': visit_id,
                'severity': new_severity,
                'score': severity_score
            }
        )
    
    async def notify_vital_deterioration(
        self,
        patient_id: str,
        patient_name: str,
        visit_id: str,
        abnormalities: List[str]
    ):
        """Notify when patient vitals show deterioration"""
        
        abnormalities_str = ', '.join(abnormalities[:3])
        message = f"⚠️ {patient_name}'s vital signs abnormal: {abnormalities_str}"
        
        await self.create_alert(
            alert_type='vital_deterioration',
            patient_id=patient_id,
            patient_name=patient_name,
            visit_id=visit_id,
            message=message,
            data={'abnormalities': abnormalities}
        )
        
        await self.send_notification_to_doctors(
            alert_type='vital_deterioration',
            message=message,
            data={
                'patient_id': patient_id,
                'visit_id': visit_id,
                'abnormalities': abnormalities
            }
        )
    
    async def notify_long_wait(
        self,
        patient_id: str,
        patient_name: str,
        visit_id: str,
        wait_time_minutes: int,
        severity_level: str
    ):
        """Notify when patient has been waiting too long"""
        
        message = f"⏰ {patient_name} ({severity_level.upper()}) has been waiting for {wait_time_minutes} minutes"
        
        await self.create_alert(
            alert_type='long_wait',
            patient_id=patient_id,
            patient_name=patient_name,
            visit_id=visit_id,
            message=message,
            data={
                'wait_time_minutes': wait_time_minutes,
                'severity_level': severity_level
            }
        )
        
        await self.send_notification_to_doctors(
            alert_type='long_wait',
            message=message,
            data={
                'patient_id': patient_id,
                'visit_id': visit_id,
                'wait_time': wait_time_minutes
            }
        )
    
    async def notify_follow_up_worsening(
        self,
        patient_id: str,
        patient_name: str,
        visit_id: str,
        original_score: int,
        new_score: int
    ):
        """Notify when follow-up shows condition worsening"""
        
        score_increase = new_score - original_score
        message = f"⚠️ {patient_name}'s condition worsened on follow-up. Severity increased by {score_increase} points (now {new_score})"
        
        await self.create_alert(
            alert_type='follow_up_worsening',
            patient_id=patient_id,
            patient_name=patient_name,
            visit_id=visit_id,
            message=message,
            data={
                'original_score': original_score,
                'new_score': new_score,
                'score_change': score_increase
            }
        )
        
        await self.send_notification_to_doctors(
            alert_type='follow_up_worsening',
            message=message,
            data={
                'patient_id': patient_id,
                'visit_id': visit_id,
                'new_score': new_score
            }
        )
    
    async def get_active_alerts(self) -> List[Dict]:
        """Get all unacknowledged alerts"""
        return await firebase_service.get_active_alerts()
    
    async def acknowledge_alert(self, alert_id: str, doctor_id: str) -> bool:
        """Mark an alert as acknowledged"""
        return await firebase_service.acknowledge_alert(alert_id, doctor_id)
    
    async def get_all_doctor_ids(self) -> List[str]:
        """Get all registered doctor IDs"""
        # This would normally query the doctors collection
        # For now, return a placeholder - implement based on your user management
        return ['doctor_001', 'doctor_002']  # Replace with actual query

# Singleton instance
notification_service = NotificationService()