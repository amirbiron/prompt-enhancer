"""
Parameter Validator Agent
זיהוי פרמטרים חסרים בפרומפט לפי קטגוריה
"""
import json
import logging
from typing import List, Dict, Any
import google.generativeai as genai

from config import config
from core.models import PromptCategory, MissingParameter

logger = logging.getLogger(__name__)


# פרמטרים נדרשים/מומלצים לכל קטגוריה
CATEGORY_PARAMETERS: Dict[PromptCategory, List[Dict[str, Any]]] = {
    PromptCategory.CODE: [
        {
            "name": "programming_language",
            "question": "באיזו שפת תכנות?",
            "importance": "required",
            "examples": ["Python", "JavaScript", "TypeScript"]
        },
        {
            "name": "framework",
            "question": "האם יש framework ספציפי? (למשל Flask, React)",
            "importance": "recommended",
            "examples": ["Flask", "FastAPI", "React", "None"]
        },
        {
            "name": "input_format",
            "question": "איך ייראה הקלט?",
            "importance": "required",
            "examples": ["JSON", "CSV", "string", "file path"]
        },
        {
            "name": "output_format",
            "question": "איך ייראה הפלט?",
            "importance": "required",
            "examples": ["JSON", "print to console", "return value"]
        },
        {
            "name": "error_handling",
            "question": "איך לטפל בשגיאות?",
            "importance": "recommended",
            "examples": ["raise exception", "return None", "log and continue"]
        }
    ],
    PromptCategory.CREATIVE: [
        {
            "name": "tone",
            "question": "באיזה טון לכתוב? (פורמלי/ידידותי/הומוריסטי)",
            "importance": "required",
            "examples": ["פורמלי", "ידידותי", "מקצועי", "הומוריסטי"]
        },
        {
            "name": "target_audience",
            "question": "למי התוכן מיועד?",
            "importance": "required",
            "examples": ["מפתחים", "מנהלים", "צעירים", "כולם"]
        },
        {
            "name": "length",
            "question": "מה האורך המבוקש?",
            "importance": "recommended",
            "examples": ["פסקה אחת", "5 נקודות", "500 מילים"]
        },
        {
            "name": "call_to_action",
            "question": "מה הפעולה שאתה רוצה שהקורא יעשה?",
            "importance": "recommended",
            "examples": ["להירשם", "לקרוא עוד", "לשתף", "אין"]
        }
    ],
    PromptCategory.ANALYSIS: [
        {
            "name": "data_source",
            "question": "מאיפה הנתונים מגיעים?",
            "importance": "required",
            "examples": ["Excel", "Database", "API", "provided text"]
        },
        {
            "name": "analysis_type",
            "question": "איזה סוג ניתוח נדרש?",
            "importance": "required",
            "examples": ["השוואה", "מגמות", "סיכום", "תובנות"]
        },
        {
            "name": "output_format",
            "question": "באיזה פורמט להציג את התוצאות?",
            "importance": "required",
            "examples": ["טבלה", "נקודות", "גרף", "דו\"ח מפורט"]
        },
        {
            "name": "depth",
            "question": "עד כמה לרדת לעומק?",
            "importance": "recommended",
            "examples": ["סקירה כללית", "ניתוח מעמיק", "executive summary"]
        }
    ],
    PromptCategory.BUSINESS: [
        {
            "name": "business_goal",
            "question": "מה המטרה העסקית?",
            "importance": "required",
            "examples": ["הגדלת מכירות", "חיסכון בעלויות", "גיוס לקוחות"]
        },
        {
            "name": "constraints",
            "question": "מה האילוצים? (תקציב, זמן, משאבים)",
            "importance": "required",
            "examples": ["תקציב 10K", "חודש אחד", "צוות של 3"]
        },
        {
            "name": "success_metrics",
            "question": "איך תמדוד הצלחה?",
            "importance": "required",
            "examples": ["ROI", "conversion rate", "NPS"]
        }
    ],
    PromptCategory.EDUCATION: [
        {
            "name": "student_level",
            "question": "מה רמת הידע של הלומד?",
            "importance": "required",
            "examples": ["מתחיל", "בינוני", "מתקדם"]
        },
        {
            "name": "learning_goal",
            "question": "מה הלומד צריך לדעת בסוף?",
            "importance": "required",
            "examples": ["להבין concept", "לדעת לעשות X", "לזכור Y"]
        },
        {
            "name": "format",
            "question": "באיזה פורמט? (הסבר, תרגילים, דוגמאות)",
            "importance": "recommended",
            "examples": ["הסבר + דוגמאות", "תרגילים", "שאלות ותשובות"]
        }
    ],
    PromptCategory.GENERAL: [
        {
            "name": "goal",
            "question": "מה המטרה הסופית?",
            "importance": "required",
            "examples": []
        },
        {
            "name": "format",
            "question": "באיזה פורמט התשובה?",
            "importance": "recommended",
            "examples": ["טקסט חופשי", "נקודות", "טבלה"]
        }
    ]
}


class ParameterValidator:
    """
    סוכן שמזהה פרמטרים חסרים בפרומפט.
    משתמש ב-AI לזיהוי חכם (לא רק keyword matching).
    """
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    async def validate(
        self, 
        prompt: str, 
        category: PromptCategory
    ) -> List[MissingParameter]:
        """
        מזהה פרמטרים חסרים בפרומפט.
        
        Args:
            prompt: הפרומפט לבדיקה
            category: הקטגוריה שזוהתה
            
        Returns:
            רשימת פרמטרים חסרים
        """
        expected_params = CATEGORY_PARAMETERS.get(category, CATEGORY_PARAMETERS[PromptCategory.GENERAL])
        
        # בדיקה עם AI
        validation_prompt = f"""[בדיקת פרמטרים - עברית]

פרומפט: "{prompt}"
קטגוריה: {category.value}

הפרמטרים הצפויים לקטגוריה זו:
{json.dumps(expected_params, ensure_ascii=False, indent=2)}

לכל פרמטר, בדוק האם הוא מוזכר בפרומפט (גם אם במילים אחרות או באופן משתמע).

החזר JSON:
{{
    "found": [
        {{"name": "...", "value_in_prompt": "מה שנמצא בפרומפט"}}
    ],
    "missing": [
        {{"name": "...", "question": "שאלה בעברית", "importance": "required|recommended"}}
    ]
}}

הערות:
- אם פרמטר משתמע מההקשר, הוא "found"
- אם פרמטר לא רלוונטי לפרומפט הספציפי, אל תכלול אותו ב-missing
- התמקד רק בפרמטרים שבאמת יעזרו לשפר את הפרומפט"""

        try:
            response = await self.model.generate_content_async(
                validation_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            
            result = json.loads(response.text)
            
            missing = [
                MissingParameter(
                    name=p["name"],
                    question=p["question"],
                    importance=p.get("importance", "recommended")
                )
                for p in result.get("missing", [])
            ]
            
            # לוג מה נמצא (לדיבוג)
            found = result.get("found", [])
            logger.debug(f"Found parameters: {[f['name'] for f in found]}")
            logger.debug(f"Missing parameters: {[m.name for m in missing]}")
            
            return missing
            
        except Exception as e:
            logger.error(f"Parameter validation failed: {e}")
            # fallback - החזר רשימה ריקה
            return []
    
    def get_questions_for_missing(
        self, 
        missing_params: List[MissingParameter],
        max_questions: int = 3
    ) -> List[str]:
        """
        מחזיר רשימת שאלות לשאול את המשתמש.
        ממיין לפי חשיבות ומגביל כמות.
        """
        # קודם required, אחר כך recommended
        sorted_params = sorted(
            missing_params,
            key=lambda p: (0 if p.importance == "required" else 1)
        )
        
        questions = []
        for param in sorted_params[:max_questions]:
            importance_mark = "❗" if param.importance == "required" else "💭"
            questions.append(f"{importance_mark} {param.question}")
        
        return questions
