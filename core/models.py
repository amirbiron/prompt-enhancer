"""
Core Models - Pydantic schemas
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class PromptCategory(str, Enum):
    """קטגוריות פרומפטים"""
    CODE = "code"
    CREATIVE = "creative"
    IMAGE_GENERATION = "image_generation"  # פרומפטים ליצירת תמונות (Midjourney, DALL-E וכו')
    ANALYSIS = "analysis"
    BUSINESS = "business"
    EDUCATION = "education"
    GENERAL = "general"


class Weakness(BaseModel):
    """נקודת חולשה בפרומפט"""
    type: str = Field(..., description="סוג החולשה: ambiguity, context, assumption, format, specificity")
    description: str = Field(..., description="תיאור הבעיה בעברית")
    suggestion: str = Field(..., description="הצעה לתיקון")
    severity: str = Field(default="medium", description="חומרה: low, medium, high")


class MissingParameter(BaseModel):
    """פרמטר חסר"""
    name: str
    question: str = Field(..., description="שאלה למשתמש בעברית")
    importance: str = Field(default="recommended", description="required או recommended")


class ProTip(BaseModel):
    """טיפ מקצועי לשדרוג הפרומפט"""
    technique: str = Field(..., description="שם הטכניקה: role_playing, chain_of_thought, few_shot, constraints, structure, creativity")
    title: str = Field(..., description="כותרת קצרה בעברית")
    suggestion: str = Field(..., description="ההצעה המלאה בעברית")
    example: Optional[str] = Field(default=None, description="דוגמה קונקרטית איך ליישם")
    impact: str = Field(default="medium", description="השפעה צפויה: low, medium, high")


class CritiqueResult(BaseModel):
    """תוצאת ביקורת"""
    weaknesses: List[Weakness] = Field(default_factory=list)
    missing_params: List[MissingParameter] = Field(default_factory=list)
    pro_tips: List[ProTip] = Field(default_factory=list, description="טיפים מקצועיים לשדרוג")
    overall_score: int = Field(default=5, ge=1, le=10, description="ציון כללי 1-10")
    is_ready: bool = Field(default=False, description="האם הפרומפט מוכן לשימוש כמו שהוא")


class RefinementResult(BaseModel):
    """תוצאת שיפור"""
    original_prompt: str
    improved_prompt: str
    category: PromptCategory
    critique: CritiqueResult
    iterations_used: int = Field(default=1)
    explanation: str = Field(default="", description="הסבר לשיפורים בעברית")
    improvement_delta: int = Field(default=0, description="שיפור בציון")


class PromptHistory(BaseModel):
    """היסטוריית פרומפט לשמירה ב-MongoDB"""
    user_id: str
    original_prompt: str
    improved_prompt: str
    category: PromptCategory
    weaknesses: List[Dict[str, Any]]
    score_before: int
    score_after: int
    iterations: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    feedback: Optional[str] = None  # משוב מהמשתמש
    rating: Optional[int] = None  # דירוג 1-5


class UserSession(BaseModel):
    """סשן משתמש לניהול מצב בשיחה"""
    user_id: str
    current_prompt: Optional[str] = None
    current_category: Optional[PromptCategory] = None
    awaiting_response: Optional[str] = None  # מה מחכים מהמשתמש
    pending_questions: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
