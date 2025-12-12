import spacy
import re
from typing import Dict, List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
import pickle
import os
from config import settings

class AITriageEngine:
    def __init__(self):
        # Load SpaCy model for NLP
        try:
            self.nlp = spacy.load(settings.NLP_MODEL)
        except:
            print("Downloading SpaCy model...")
            os.system(f"python -m spacy download {settings.NLP_MODEL}")
            self.nlp = spacy.load(settings.NLP_MODEL)
        
        # Emergency keywords for rule-based overrides
        self.emergency_keywords = settings.EMERGENCY_KEYWORDS
        
        # Symptom severity mapping (example training data)
        self.symptom_severity_map = {
            # Critical symptoms (70-100)
            'chest pain': 95, 'heart attack': 100, 'stroke': 100, 'unconscious': 100,
            'difficulty breathing': 90, 'severe bleeding': 95, 'seizure': 90,
            'anaphylaxis': 95, 'overdose': 95, 'severe head injury': 90,
            'choking': 95, 'severe burns': 85, 'suicide': 100,
            
            # Moderate symptoms (40-69)
            'high fever': 65, 'severe pain': 60, 'vomiting': 55, 'diarrhea': 50,
            'abdominal pain': 60, 'broken bone': 65, 'severe headache': 60,
            'moderate bleeding': 55, 'allergic reaction': 60, 'dehydration': 55,
            'infected wound': 50, 'persistent cough': 45, 'back pain': 50,
            
            # Normal/mild symptoms (0-39)
            'mild headache': 25, 'common cold': 20, 'sore throat': 25,
            'minor cut': 15, 'mild fever': 30, 'runny nose': 15,
            'mild cough': 20, 'minor rash': 20, 'fatigue': 25,
            'mild nausea': 25, 'minor pain': 20, 'bruise': 15
        }
        
        # Vital signs thresholds for abnormality detection
        self.vital_thresholds = {
            'temperature': {'critical_low': 35.5, 'low': 36.0, 'high': 38.0, 'critical_high': 39.5},
            'heart_rate': {'critical_low': 50, 'low': 60, 'high': 100, 'critical_high': 120},
            'blood_pressure_systolic': {'critical_low': 90, 'low': 100, 'high': 140, 'critical_high': 180},
            'blood_pressure_diastolic': {'critical_low': 60, 'low': 70, 'high': 90, 'critical_high': 110},
            'respiratory_rate': {'critical_low': 10, 'low': 12, 'high': 20, 'critical_high': 30},
            'oxygen_saturation': {'critical_low': 90, 'low': 95, 'high': 100, 'critical_high': 100}
        }
    
    def extract_symptoms(self, text: str) -> List[str]:
        """Extract symptoms from text using NLP"""
        doc = self.nlp(text.lower())
        
        symptoms = []
        
        # Extract noun phrases and named entities
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) <= 4:  # Limit phrase length
                symptoms.append(chunk.text)
        
        # Extract medical entities if available
        for ent in doc.ents:
            if ent.label_ in ['SYMPTOM', 'DISEASE', 'CONDITION']:
                symptoms.append(ent.text)
        
        # Match against known symptoms
        for symptom in self.symptom_severity_map.keys():
            if symptom in text.lower():
                if symptom not in symptoms:
                    symptoms.append(symptom)
        
        return list(set(symptoms))  # Remove duplicates
    
    def check_emergency_keywords(self, text: str) -> Tuple[bool, List[str]]:
        """Check for emergency keywords that trigger immediate critical triage"""
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.emergency_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return len(found_keywords) > 0, found_keywords
    
    def analyze_vitals(self, vitals: Dict) -> Tuple[int, List[str]]:
        """Analyze vital signs and return severity score and abnormalities"""
        score = 0
        abnormalities = []
        
        for vital_name, value in vitals.items():
            if value is None or vital_name not in self.vital_thresholds:
                continue
            
            thresholds = self.vital_thresholds[vital_name]
            
            if value <= thresholds['critical_low'] or value >= thresholds['critical_high']:
                score += 30
                abnormalities.append(f"Critical {vital_name}: {value}")
            elif value <= thresholds['low'] or value >= thresholds['high']:
                score += 15
                abnormalities.append(f"Abnormal {vital_name}: {value}")
        
        return min(score, 50), abnormalities  # Cap vitals contribution at 50
    
    def calculate_symptom_severity(self, symptoms: List[str], symptom_text: str) -> int:
        """Calculate severity score based on detected symptoms"""
        if not symptoms:
            # Use basic text analysis if no specific symptoms detected
            severity_indicators = {
                'severe': 20, 'extreme': 25, 'unbearable': 25, 'intense': 15,
                'terrible': 15, 'awful': 15, 'bad': 10, 'moderate': 5, 'mild': -5
            }
            
            score = 30  # Base score
            for indicator, value in severity_indicators.items():
                if indicator in symptom_text.lower():
                    score += value
            
            return min(max(score, 0), 70)
        
        # Calculate based on known symptoms
        max_severity = 0
        avg_severity = 0
        
        for symptom in symptoms:
            # Check exact match
            if symptom in self.symptom_severity_map:
                severity = self.symptom_severity_map[symptom]
                max_severity = max(max_severity, severity)
                avg_severity += severity
            else:
                # Partial match
                for known_symptom, severity in self.symptom_severity_map.items():
                    if known_symptom in symptom or symptom in known_symptom:
                        max_severity = max(max_severity, severity)
                        avg_severity += severity
                        break
        
        if len(symptoms) > 0:
            avg_severity = avg_severity / len(symptoms)
        
        # Weight toward maximum severity but consider average
        final_score = (max_severity * 0.7) + (avg_severity * 0.3)
        return int(final_score)
    
    def predict_severity(self, symptom_text: str, vitals: Dict, duration: str = None) -> Dict:
        """
        Main prediction function that combines NLP, rule-based logic, and vital analysis
        Returns comprehensive triage result
        """
        # Step 1: Check for emergency keywords (rule-based override)
        is_emergency, emergency_flags = self.check_emergency_keywords(symptom_text)
        
        if is_emergency:
            return {
                'severity_score': 100,
                'severity_level': 'critical',
                'priority': 1,
                'symptoms_detected': emergency_flags,
                'emergency_flags': emergency_flags,
                'vital_abnormalities': [],
                'ai_reasoning': f"Emergency keywords detected: {', '.join(emergency_flags)}. Immediate medical attention required.",
                'rule_based_override': True,
                'recommendation': "IMMEDIATE EMERGENCY CARE REQUIRED"
            }
        
        # Step 2: Extract symptoms using NLP
        symptoms = self.extract_symptoms(symptom_text)
        
        # Step 3: Calculate symptom severity
        symptom_score = self.calculate_symptom_severity(symptoms, symptom_text)
        
        # Step 4: Analyze vitals
        vital_score, vital_abnormalities = self.analyze_vitals(vitals)
        
        # Step 5: Combine scores (weighted)
        total_score = int((symptom_score * 0.7) + (vital_score * 0.3))
        
        # Apply duration modifier
        if duration:
            if 'chronic' in duration.lower() or 'weeks' in duration.lower() or 'months' in duration.lower():
                total_score = min(total_score, 65)  # Chronic conditions rarely critical
            elif 'sudden' in duration.lower() or 'acute' in duration.lower():
                total_score = min(total_score + 10, 100)  # Sudden onset more concerning
        
        # Step 6: Determine severity level and priority
        if total_score >= settings.CRITICAL_MIN:
            severity_level = 'critical'
            priority = 1
            recommendation = "Immediate medical attention required. Priority patient."
        elif total_score >= settings.MODERATE_MIN:
            severity_level = 'moderate'
            priority = 2
            recommendation = "Medical evaluation needed soon. Moderate priority."
        else:
            severity_level = 'normal'
            priority = 3
            recommendation = "Standard consultation. Can wait for available slot."
        
        # Step 7: Generate AI reasoning
        reasoning_parts = []
        reasoning_parts.append(f"Symptom analysis score: {symptom_score}/100")
        if vital_abnormalities:
            reasoning_parts.append(f"Vital signs abnormalities detected: {', '.join(vital_abnormalities)}")
        if symptoms:
            reasoning_parts.append(f"Detected symptoms: {', '.join(symptoms[:5])}")
        reasoning_parts.append(f"Final severity assessment: {total_score}/100 ({severity_level})")
        
        ai_reasoning = " | ".join(reasoning_parts)
        
        return {
            'severity_score': total_score,
            'severity_level': severity_level,
            'priority': priority,
            'symptoms_detected': symptoms[:10],  # Limit to top 10
            'emergency_flags': emergency_flags,
            'vital_abnormalities': vital_abnormalities,
            'ai_reasoning': ai_reasoning,
            'rule_based_override': False,
            'recommendation': recommendation
        }
    
    def reassess_severity(self, original_score: int, follow_up_text: str, condition_change: str) -> Dict:
        """Reassess severity based on follow-up information"""
        # Extract new symptoms
        symptoms = self.extract_symptoms(follow_up_text)
        
        # Adjust score based on condition change
        if condition_change == 'worsened':
            new_score = min(original_score + 20, 100)
            reasoning = "Condition has worsened. Severity increased."
        elif condition_change == 'improved':
            new_score = max(original_score - 15, 0)
            reasoning = "Condition has improved. Severity reduced."
        else:  # same
            new_score = original_score
            reasoning = "Condition remains stable."
        
        # Check for new emergency keywords
        is_emergency, emergency_flags = self.check_emergency_keywords(follow_up_text)
        if is_emergency:
            new_score = 100
            reasoning += f" NEW EMERGENCY: {', '.join(emergency_flags)}"
        
        # Determine new severity level
        if new_score >= settings.CRITICAL_MIN:
            severity_level = 'critical'
            priority = 1
        elif new_score >= settings.MODERATE_MIN:
            severity_level = 'moderate'
            priority = 2
        else:
            severity_level = 'normal'
            priority = 3
        
        return {
            'severity_score': new_score,
            'severity_level': severity_level,
            'priority': priority,
            'symptoms_detected': symptoms,
            'emergency_flags': emergency_flags,
            'ai_reasoning': reasoning,
            'score_change': new_score - original_score
        }

# Singleton instance
ai_engine = AITriageEngine()