import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API Settings
    API_TITLE: str = "AI Triage System API"
    API_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Firebase Configuration
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "firebase-credentials.json")
    FIREBASE_API_KEY: str = "AIzaSyBfpFP2etJ2tDw5TmV-sT0A5MxWsOcGgNY"
    FIREBASE_AUTH_DOMAIN: str = "ai-health-and-triage-app.firebaseapp.com"
    FIREBASE_PROJECT_ID: str = "ai-health-and-triage-app"
    FIREBASE_STORAGE_BUCKET: str = "ai-health-and-triage-app.firebasestorage.app"
    FIREBASE_MESSAGING_SENDER_ID: str = "962145261534"
    FIREBASE_APP_ID: str = "1:962145261534:web:283c70b80314d88c4e2f4f"
    FIREBASE_MEASUREMENT_ID: str = "G-H1ZKD7W436"
    
    # AI Model Settings
    AI_MODEL_PATH: str = "models/triage_model.pkl"
    NLP_MODEL: str = "en_core_web_sm"
    
    # Severity Thresholds
    NORMAL_MAX: int = 39
    MODERATE_MIN: int = 40
    MODERATE_MAX: int = 69
    CRITICAL_MIN: int = 70
    
    # Emergency Keywords (Rule-based overrides)
    EMERGENCY_KEYWORDS: list = [
        "chest pain", "difficulty breathing", "unconscious", "severe bleeding",
        "stroke symptoms", "heart attack", "seizure", "suicide", "overdose",
        "severe head injury", "choking", "anaphylaxis", "severe burns"
    ]
    
    # CORS Settings
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://your-frontend-domain.com"
    ]
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()