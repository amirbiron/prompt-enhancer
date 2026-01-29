"""
Category Router Agent
זיהוי אוטומטי של קטגוריית הפרומפט
"""
import json
import logging
from typing import Tuple
import google.generativeai as genai

from config import config
from core.models import PromptCategory

logger = logging.getLogger(__name__)


class CategoryRouter:
    """
    סוכן שמזהה את הקטגוריה של פרומפט.
    משתמש במודל קטן ומהיר לחיסכון.
    """
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
        # מילות מפתח לזיהוי מהיר (fallback)
        self.keyword_hints = {
            PromptCategory.CODE: [
                "קוד", "סקריפט", "פונקציה", "תכנות", "python", "javascript",
                "api", "באג", "debug", "function", "class", "מחלקה"
            ],
            PromptCategory.IMAGE_GENERATION: [
                "midjourney", "dall-e", "dalle", "stable diffusion", "תמונה",
                "אילוסטרציה", "ציור", "רנדר", "render", "3d", "פוטוריאליסטי",
                "אנימה", "קריקטורה", "דיוקן", "נוף", "לוגו", "איור",
                "ויזואלי", "גרפי", "עיצוב תמונה", "image", "photo", "art style",
                "aspect ratio", "cinematic", "realistic", "hyper realistic"
            ],
            PromptCategory.CREATIVE: [
                "כתוב", "סיפור", "שיר", "פוסט", "קופי", "שיווק", "יצירתי",
                "תוכן", "בלוג", "מאמר", "פרסום", "סלוגן"
            ],
            PromptCategory.ANALYSIS: [
                "נתח", "ניתוח", "השווה", "סקור", "דו\"ח", "מחקר",
                "data", "נתונים", "סטטיסטיקה", "מגמות"
            ],
            PromptCategory.BUSINESS: [
                "עסקי", "אסטרטגיה", "תקציב", "roi", "לקוח", "מכירות",
                "שיווק", "תכנית עסקית", "pitch", "משקיע"
            ],
            PromptCategory.EDUCATION: [
                "הסבר", "למד", "תרגיל", "שיעור", "קורס", "מורה",
                "תלמיד", "חינוך", "tutorial", "guide"
            ]
        }
    
    async def detect_category(self, prompt: str) -> Tuple[PromptCategory, float]:
        """
        מזהה את הקטגוריה של פרומפט.
        
        Args:
            prompt: הפרומפט לזיהוי
            
        Returns:
            tuple של (קטגוריה, רמת ביטחון 0-1)
        """
        # ניסיון ראשון: זיהוי עם AI
        try:
            category, confidence = await self._detect_with_ai(prompt)
            if confidence >= 0.7:
                return category, confidence
        except Exception as e:
            logger.warning(f"AI detection failed, using fallback: {e}")
        
        # fallback: זיהוי לפי מילות מפתח
        return self._detect_with_keywords(prompt)
    
    async def _detect_with_ai(self, prompt: str) -> Tuple[PromptCategory, float]:
        """זיהוי עם AI"""
        detection_prompt = f"""[זיהוי קטגוריה - עברית]

פרומפט: "{prompt}"

בחר את הקטגוריה המתאימה ביותר:
- code: כתיבת קוד, סקריפטים, תכנות, debugging
- image_generation: פרומפטים ליצירת תמונות (Midjourney, DALL-E, Stable Diffusion וכו')
- creative: כתיבה יצירתית טקסטואלית, שיווק, תוכן, סיפורים (לא תמונות!)
- analysis: ניתוח נתונים, מחקר, השוואות, דוחות
- business: החלטות עסקיות, אסטרטגיה, מכירות
- education: הסברים, לימוד, הדרכות, תרגילים
- general: כל השאר

שים לב: אם הפרומפט מיועד ליצירת תמונה (מזכיר Midjourney, DALL-E, תמונה, אילוסטרציה, ציור וכו') - זה image_generation!

החזר JSON:
{{
    "category": "code|image_generation|creative|analysis|business|education|general",
    "confidence": 0.0-1.0,
    "reasoning": "הסבר קצר"
}}"""

        response = await self.model.generate_content_async(
            detection_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.1
            }
        )
        
        result = json.loads(response.text)
        category = PromptCategory(result["category"])
        confidence = float(result["confidence"])
        
        logger.debug(f"AI detected: {category} ({confidence:.2f}) - {result.get('reasoning', '')}")
        
        return category, confidence
    
    def _detect_with_keywords(self, prompt: str) -> Tuple[PromptCategory, float]:
        """זיהוי לפי מילות מפתח (fallback)"""
        prompt_lower = prompt.lower()
        scores = {}
        
        for category, keywords in self.keyword_hints.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > 0:
                scores[category] = score
        
        if not scores:
            return PromptCategory.GENERAL, 0.3
        
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        confidence = min(0.9, 0.3 + (max_score * 0.15))
        
        return best_category, confidence
    
    def get_category_description(self, category: PromptCategory) -> str:
        """מחזיר תיאור הקטגוריה בעברית"""
        descriptions = {
            PromptCategory.CODE: "💻 קוד ותכנות",
            PromptCategory.IMAGE_GENERATION: "🎨 יצירת תמונות",
            PromptCategory.CREATIVE: "✍️ כתיבה יצירתית",
            PromptCategory.ANALYSIS: "📊 ניתוח ומחקר",
            PromptCategory.BUSINESS: "💼 עסקים ואסטרטגיה",
            PromptCategory.EDUCATION: "📚 חינוך ולימוד",
            PromptCategory.GENERAL: "🌐 כללי"
        }
        return descriptions.get(category, "🌐 כללי")
