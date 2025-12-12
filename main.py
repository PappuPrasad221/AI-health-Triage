from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import auth, patient, triage, doctor
import asyncio
from typing import List
import json

# Initialize FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="AI-powered Smart Triage & Virtual Health Assistant System"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(patient.router, prefix=settings.API_PREFIX)
app.include_router(triage.router, prefix=settings.API_PREFIX)
app.include_router(doctor.router, prefix=settings.API_PREFIX)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# WebSocket endpoint for real-time updates
@app.websocket("/ws/queue")
async def websocket_queue_updates(websocket: WebSocket):
    """
    WebSocket endpoint for real-time queue updates
    Sends queue updates to all connected doctors
    """
    await manager.connect(websocket)
    
    try:
        # Send initial queue state
        from services.queue_manager import queue_manager
        initial_queue = await queue_manager.get_queue_statistics()
        await websocket.send_json({
            "type": "initial_queue",
            "data": initial_queue
        })
        
        # Keep connection alive and listen for messages
        while True:
            try:
                # Receive any messages from client (heartbeat, etc.)
                data = await websocket.receive_text()
                
                # If client sends "refresh", send updated queue
                if data == "refresh":
                    updated_queue = await queue_manager.get_queue_statistics()
                    await websocket.send_json({
                        "type": "queue_update",
                        "data": updated_queue
                    })
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
    
    finally:
        manager.disconnect(websocket)

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """
    WebSocket endpoint for real-time alerts
    """
    await manager.connect(websocket)
    
    try:
        from services.notification_service import notification_service
        
        # Send initial alerts
        initial_alerts = await notification_service.get_active_alerts()
        await websocket.send_json({
            "type": "initial_alerts",
            "data": initial_alerts
        })
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                
                if data == "refresh":
                    updated_alerts = await notification_service.get_active_alerts()
                    await websocket.send_json({
                        "type": "alerts_update",
                        "data": updated_alerts
                    })
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break
    
    finally:
        manager.disconnect(websocket)

# Background task to check for long-waiting patients
async def check_long_wait_task():
    """Background task that checks for patients waiting too long"""
    from services.queue_manager import queue_manager
    from services.notification_service import notification_service
    
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            long_wait_patients = await queue_manager.check_long_wait_patients()
            
            for patient_info in long_wait_patients:
                entry = patient_info['entry']
                wait_time = patient_info['wait_time_minutes']
                
                await notification_service.notify_long_wait(
                    patient_id=entry['patient_id'],
                    patient_name=entry['patient_name'],
                    visit_id=entry['visit_id'],
                    wait_time_minutes=wait_time,
                    severity_level=entry['severity_level']
                )
                
                # Broadcast to all connected doctors
                await manager.broadcast({
                    "type": "long_wait_alert",
                    "data": patient_info
                })
        
        except Exception as e:
            print(f"Long wait check error: {e}")

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    asyncio.create_task(check_long_wait_task())

@app.get("/")
async def root():
    """API Root endpoint"""
    return {
        "message": "AI Smart Triage & Virtual Health Assistant API",
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2025-01-15T00:00:00Z"
    }

# Broadcast helper function (can be called from other modules)
async def broadcast_queue_update(queue_data: dict):
    """Helper function to broadcast queue updates"""
    await manager.broadcast({
        "type": "queue_update",
        "data": queue_data
    })

async def broadcast_alert(alert_data: dict):
    """Helper function to broadcast new alerts"""
    await manager.broadcast({
        "type": "new_alert",
        "data": alert_data
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)