"""
Real AI Service for Medical Triage Analysis
Supports both OpenAI (GPT-4) and Anthropic (Claude) APIs
"""

import json
import aiohttp
from typing import Dict, List, Optional
from config import settings

class RealAITriageEngine:
    """
    Advanced AI-powered medical triage engine using real LLM APIs
    """
    
    def __init__(self):
        self.provider = settings.AI_MODEL_PROVIDER
        self.openai_key = settings.OPENAI_API_KEY
        self.anthropic_key = settings.ANTHROPIC_API_KEY
        
        # Validate API keys
        if self.provider == "openai" and not self.openai_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in environment.")
        if self.provider == "anthropic" and not self.anthropic_key:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in environment.")
    
    def _build_medical_prompt(self, symptom_text: str, vitals: Dict, age: int, 
                             pain_level: int, duration: str, comorbidities: List[str]) -> str:
        """Build comprehensive medical prompt for AI analysis"""
        
        prompt = f"""You are an expert emergency medicine physician AI assistant. Analyze this patient case and provide a comprehensive triage assessment.

PATIENT INFORMATION:
- Age: {age} years old
- Pain Level: {pain_level}/10
- Duration of Symptoms: {duration or 'Not specified'}
- Pre-existing Conditions: {', '.join(comorbidities) if comorbidities else 'None reported'}

CHIEF COMPLAINT & SYMPTOMS:
{symptom_text}

VITAL SIGNS:
- Temperature: {vitals.get('temperature', 'Not recorded')}°C
- Heart Rate: {vitals.get('heart_rate', 'Not recorded')} bpm
- Blood Pressure: {vitals.get('blood_pressure_systolic', 'Not recorded')}/{vitals.get('blood_pressure_diastolic', 'Not recorded')} mmHg
- Respiratory Rate: {vitals.get('respiratory_rate', 'Not recorded')} breaths/min
- Oxygen Saturation: {vitals.get('oxygen_saturation', 'Not recorded')}%

TASK: Provide a comprehensive medical triage assessment. Respond ONLY with valid JSON (no markdown, no code blocks):

{{
  "severity_score": <integer 0-100>,
  "severity_level": "<critical|moderate|normal>",
  "priority": <1|2|3>,
  "emergency_flags": ["<critical symptom 1>", "<critical symptom 2>"],
  "detected_symptoms": ["<symptom 1>", "<symptom 2>", "<symptom 3>"],
  "vital_abnormalities": ["<abnormality 1 with value>", "<abnormality 2 with value>"],
  "differential_diagnosis": [
    {{"diagnosis": "<condition name>", "probability": <0-100>}},
    {{"diagnosis": "<condition name>", "probability": <0-100>}}
  ],
  "clinical_concerns": ["<concern 1>", "<concern 2>"],
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"],
  "reasoning": "<detailed 2-3 sentence explanation of severity assessment>",
  "confidence": <0-100>
}}

SCORING GUIDELINES:
- 0-39 (Normal): Minor conditions, stable vitals, can wait 30+ minutes
- 40-69 (Moderate): Concerning symptoms, some vital abnormalities, see within 15-30 minutes
- 70-100 (Critical): Life-threatening, severe vital instability, immediate attention required

Consider: symptom severity, vital sign patterns, age risk factors, comorbidity impact, pain intensity, and symptom onset acuity.
Priority: 1=Critical (immediate), 2=Moderate (urgent), 3=Normal (standard)

Provide top 3-5 differential diagnoses with probability estimates based on clinical presentation."""

        return prompt
    
    async def analyze_with_openai(self, prompt: str) -> Dict:
        """Call OpenAI GPT-4 API"""
        
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert emergency medicine physician specializing in medical triage. Provide accurate, evidence-based assessments in JSON format only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": settings.AI_TEMPERATURE,
            "max_tokens": settings.AI_MAX_TOKENS,
            "response_format": {"type": "json_object"}
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API Error {response.status}: {error_text}")
                
                data = await response.json()
                content = data['choices'][0]['message']['content']
                return json.loads(content)
    
    async def analyze_with_anthropic(self, prompt: str) -> Dict:
        """Call Anthropic Claude API"""
        
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        
        payload = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": settings.AI_MAX_TOKENS,
            "temperature": settings.AI_TEMPERATURE,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API Error {response.status}: {error_text}")
                
                data = await response.json()
                content = data['content'][0]['text']
                
                # Extract JSON from response (Claude sometimes adds explanatory text)
                json_match = content
                if '{' in content:
                    start = content.index('{')
                    end = content.rindex('}') + 1
                    json_match = content[start:end]
                
                return json.loads(json_match)
    
    async def comprehensive_assessment(
        self,
        symptom_text: str,
        vitals: Dict,
        age: int,
        pain_level: int,
        duration: str = "",
        comorbidities: List[str] = None
    ) -> Dict:
        """
        Main assessment function - calls real AI API
        
        Returns:
            Dict with keys: score, level, priority, symptoms, emergencyFlags,
            vitalFlags, clinicalConcerns, differential, recommendations,
            reasoning, confidence, aiPowered
        """
        
        if comorbidities is None:
            comorbidities = []
        
        # Build prompt
        prompt = self._build_medical_prompt(
            symptom_text, vitals, age, pain_level, duration, comorbidities
        )
        
        # Call appropriate AI provider
        try:
            if self.provider == "openai":
                result = await self.analyze_with_openai(prompt)
            else:  # anthropic
                result = await self.analyze_with_anthropic(prompt)
            
            # Map API response to our format
            return {
                'score': result.get('severity_score', 50),
                'level': result.get('severity_level', 'moderate'),
                'priority': result.get('priority', 2),
                'waitTime': 0 if result.get('severity_level') == 'critical' else 
                           15 if result.get('severity_level') == 'moderate' else 30,
                'symptoms': result.get('detected_symptoms', []),
                'emergencyFlags': result.get('emergency_flags', []),
                'vitalFlags': result.get('vital_abnormalities', []),
                'clinicalConcerns': result.get('clinical_concerns', []),
                'differential': result.get('differential_diagnosis', []),
                'recommendations': result.get('recommendations', []),
                'reasoning': result.get('reasoning', 'AI analysis completed'),
                'confidence': result.get('confidence', 85),
                'aiPowered': True,
                'aiProvider': self.provider
            }
            
        except Exception as e:
            # Log error and fall back to rule-based system if configured
            print(f"AI API Error: {str(e)}")
            if settings.USE_FALLBACK_AI:
                from services.ai_engine import ai_engine
                return ai_engine.predict_severity(symptom_text, vitals, duration)
            else:
                raise Exception(f"AI Analysis Failed: {str(e)}")

# Singleton instance
real_ai_engine = RealAITriageEngine()