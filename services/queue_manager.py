from typing import List, Dict, Optional
from datetime import datetime, timedelta
import asyncio
from models.triage import QueueEntry, SeverityLevel
from services.firebase_service import firebase_service

class QueueManager:
    def __init__(self):
        self.queue_cache: List[Dict] = []
        self.wait_time_estimates = {
            'critical': 0,      # Immediate
            'moderate': 15,     # 15 minutes
            'normal': 30        # 30 minutes
        }
    
    async def add_to_queue(self, queue_entry: Dict) -> Dict:
        """Add a patient to the priority queue"""
        # Calculate estimated wait time
        queue_entry['estimated_wait_time'] = await self.calculate_wait_time(queue_entry['severity_level'])
        
        # Save to Firebase
        entry_id = await firebase_service.add_to_queue(queue_entry)
        queue_entry['id'] = entry_id
        
        # Refresh queue and update positions
        await self.refresh_queue()
        
        return queue_entry
    
    async def refresh_queue(self) -> List[Dict]:
        """Refresh the queue from Firebase and recalculate positions"""
        # Get current queue from Firebase
        self.queue_cache = await firebase_service.get_queue()
        
        # Sort by priority (1 = highest) and then by check-in time
        self.queue_cache.sort(key=lambda x: (x['priority'], x['checked_in_at']))
        
        # Update queue positions
        for position, entry in enumerate(self.queue_cache, start=1):
            entry['queue_position'] = position
            
            # Update position in Firebase
            await firebase_service.update_queue_entry(
                entry['id'],
                {'queue_position': position}
            )
        
        return self.queue_cache
    
    async def update_severity(self, visit_id: str, new_severity_score: int, new_severity_level: str) -> Dict:
        """Update patient severity and reorder queue"""
        # Find the entry in queue
        entry = None
        for e in self.queue_cache:
            if e['visit_id'] == visit_id:
                entry = e
                break
        
        if not entry:
            return {'error': 'Entry not found in queue'}
        
        old_severity = entry['severity_level']
        old_priority = entry['priority']
        
        # Update severity
        entry['severity_score'] = new_severity_score
        entry['severity_level'] = new_severity_level
        
        # Update priority based on new severity
        if new_severity_level == 'critical':
            entry['priority'] = 1
        elif new_severity_level == 'moderate':
            entry['priority'] = 2
        else:
            entry['priority'] = 3
        
        # Update in Firebase
        await firebase_service.update_queue_entry(entry['id'], {
            'severity_score': new_severity_score,
            'severity_level': new_severity_level,
            'priority': entry['priority']
        })
        
        # Refresh queue to reorder
        await self.refresh_queue()
        
        # Check if severity changed significantly
        severity_changed = (old_severity != new_severity_level)
        position_changed = (old_priority != entry['priority'])
        
        return {
            'entry': entry,
            'severity_changed': severity_changed,
            'position_changed': position_changed,
            'old_severity': old_severity,
            'new_severity': new_severity_level
        }
    
    async def call_patient(self, visit_id: str, doctor_id: str) -> Dict:
        """Mark patient as called and in progress"""
        entry = None
        for e in self.queue_cache:
            if e['visit_id'] == visit_id:
                entry = e
                break
        
        if not entry:
            return {'error': 'Entry not found'}
        
        # Update status
        await firebase_service.update_queue_entry(entry['id'], {
            'status': 'in_progress',
            'called_at': datetime.utcnow(),
            'assigned_doctor_id': doctor_id
        })
        
        # Update visit
        await firebase_service.update_visit(visit_id, {
            'status': 'in_progress',
            'assigned_doctor_id': doctor_id
        })
        
        # Refresh queue
        await self.refresh_queue()
        
        return {'success': True, 'entry': entry}
    
    async def complete_visit(self, visit_id: str) -> Dict:
        """Mark visit as completed and remove from queue"""
        entry = None
        entry_id = None
        
        for e in self.queue_cache:
            if e['visit_id'] == visit_id:
                entry = e
                entry_id = e['id']
                break
        
        if not entry:
            return {'error': 'Entry not found'}
        
        # Remove from queue
        await firebase_service.remove_from_queue(entry_id)
        
        # Update visit status
        await firebase_service.update_visit(visit_id, {
            'status': 'completed',
            'completed_at': datetime.utcnow()
        })
        
        # Refresh queue
        await self.refresh_queue()
        
        return {'success': True}
    
    async def calculate_wait_time(self, severity_level: str) -> int:
        """Calculate estimated wait time based on queue and severity"""
        base_time = self.wait_time_estimates.get(severity_level, 30)
        
        # Count patients ahead in queue with same or higher priority
        if severity_level == 'critical':
            ahead = 0  # Critical always goes first
        elif severity_level == 'moderate':
            ahead = sum(1 for e in self.queue_cache if e['severity_level'] == 'critical')
        else:  # normal
            ahead = sum(1 for e in self.queue_cache if e['severity_level'] in ['critical', 'moderate'])
        
        # Estimate 10 minutes per patient ahead
        estimated_time = base_time + (ahead * 10)
        
        return estimated_time
    
    async def get_queue_statistics(self) -> Dict:
        """Get queue statistics"""
        await self.refresh_queue()
        
        total = len(self.queue_cache)
        critical = sum(1 for e in self.queue_cache if e['severity_level'] == 'critical')
        moderate = sum(1 for e in self.queue_cache if e['severity_level'] == 'moderate')
        normal = sum(1 for e in self.queue_cache if e['severity_level'] == 'normal')
        
        avg_wait_time = sum(e.get('estimated_wait_time', 0) for e in self.queue_cache) / total if total > 0 else 0
        
        return {
            'total_patients': total,
            'critical_count': critical,
            'moderate_count': moderate,
            'normal_count': normal,
            'average_wait_time': int(avg_wait_time),
            'queue': self.queue_cache
        }
    
    async def check_long_wait_patients(self) -> List[Dict]:
        """Check for patients waiting too long"""
        long_wait_threshold = {
            'critical': 5,      # 5 minutes
            'moderate': 30,     # 30 minutes
            'normal': 60        # 60 minutes
        }
        
        long_wait_patients = []
        current_time = datetime.utcnow()
        
        for entry in self.queue_cache:
            checked_in = entry.get('checked_in_at')
            if isinstance(checked_in, str):
                checked_in = datetime.fromisoformat(checked_in.replace('Z', '+00:00'))
            
            wait_time = (current_time - checked_in).total_seconds() / 60  # Convert to minutes
            threshold = long_wait_threshold.get(entry['severity_level'], 60)
            
            if wait_time > threshold:
                long_wait_patients.append({
                    'entry': entry,
                    'wait_time_minutes': int(wait_time),
                    'threshold_exceeded': int(wait_time - threshold)
                })
        
        return long_wait_patients

# Singleton instance
queue_manager = QueueManager()