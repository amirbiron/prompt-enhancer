"""
Shadow Critic Agent
סוכן ביקורת שמזהה נקודות חולשה בפרומפטים
"""
import json
import logging
from typing import Optional
import google.generativeai as genai

from config import config
from core.models import CritiqueResult, Weakness, MissingParameter, ProTip, PromptCategory

logger = logging.getLogger(__name__)


class ShadowCritic:
    """
    סוכן ביקורת פנימי שמנתח פרומפטים ומזהה בעיות פוטנציאליות.
    משתמש במודל זול ומהיר (Gemini Flash) לחיסכון בעלויות.
    """
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        
    async def critique(
        self, 
        prompt: str, 
        category: Optional[PromptCategory] = None
    ) -> CritiqueResult:
        """
        מבצע ביקורת על פרומפט ומחזיר נקודות חולשה והצעות לשיפור.
        
        Args:
            prompt: הפרומפט לביקורת
            category: קטגוריה (אופציונלי - אם לא סופק, יזהה אוטומטית)
        
        Returns:
            CritiqueResult עם כל הממצאים
        """
        category_context = f"קטגוריה: {category.value}" if category else "קטגוריה: לא ידועה"
        
        critique_prompt = f"""[מצב מאמן פרומפטים מקצועי - עברית]

אתה מאמן פרומפטים מומחה. התפקיד שלך הוא לא רק למצוא בעיות, אלא בעיקר **להציע רעיונות יצירתיים** שישדרגו את הפרומפט לרמה מקצועית יותר.

פרומפט לניתוח:
"{prompt}"

{category_context}

## חלק 1: זיהוי בעיות (אם יש)
זהה נקודות חולשה ב-5 קטגוריות:
1. **אמביגואיות (ambiguity)** - היכן המודל עלול להבין לא נכון?
2. **חוסר הקשר (context)** - מה חסר כדי שהמודל יבין את הכוונה?
3. **הנחות מוטעות (assumption)** - מה אתה מניח שהמודל יודע אבל הוא לא?
4. **פורמט לא ברור (format)** - איך הפלט אמור להיראות?
5. **חוסר ספציפיות (specificity)** - איפה צריך להיות יותר מדויק?

## חלק 2: טיפים מקצועיים לשדרוג (החלק החשוב!)
הצע רעיונות יצירתיים לשדרוג הפרומפט באמצעות טכניקות מתקדמות:

1. **role_playing** - הגדרת תפקיד למודל ("אתה מומחה ב...", "דמיין שאתה...")
2. **chain_of_thought** - בקשה לחשיבה שלב-אחר-שלב ("קודם נתח, אחר כך תכנן...")
3. **few_shot** - הוספת דוגמאות לפלט הרצוי
4. **constraints** - הוספת מגבלות שמחדדות ("הימנע מ...", "התמקד רק ב...")
5. **structure** - הצעה למבנה טוב יותר של הפרומפט
6. **creativity** - רעיונות יצירתיים ספציפיים לפרומפט הזה

**חשוב:** גם אם הפרומפט טוב, תמיד אפשר לשדרג אותו! תן לפחות 2-3 טיפים יצירתיים.

פנה ישירות למשתמש בגוף שני ("אתה", "לך"), לא בגוף שלישי.

החזר תשובה בפורמט JSON בלבד:
{{
    "weaknesses": [
        {{
            "type": "ambiguity|context|assumption|format|specificity",
            "description": "תיאור הבעיה בעברית",
            "suggestion": "הצעה לתיקון",
            "severity": "low|medium|high"
        }}
    ],
    "missing_params": [
        {{
            "name": "שם הפרמטר",
            "question": "שאלה למשתמש בעברית",
            "importance": "required|recommended"
        }}
    ],
    "pro_tips": [
        {{
            "technique": "role_playing|chain_of_thought|few_shot|constraints|structure|creativity",
            "title": "כותרת קצרה וקליטה",
            "suggestion": "הסבר מלא של ההצעה",
            "example": "דוגמה קונקרטית איך זה ייראה בפרומפט",
            "impact": "low|medium|high"
        }}
    ],
    "overall_score": 1-10,
    "is_ready": true/false
}}

הערות:
- **חובה לתת לפחות 2 pro_tips** גם אם הפרומפט טוב
- הטיפים צריכים להיות ספציפיים לפרומפט, לא גנריים
- תן דוגמאות קונקרטיות בשדה example
- ציון 7+ = מוכן לשימוש עם שיפורים קלים
- ציון 5-6 = צריך שיפור משמעותי
- ציון 1-4 = צריך לשכתב מחדש"""

        try:
            response = await self.model.generate_content_async(
                critique_prompt,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3  # נמוך יותר = יותר עקבי
                }
            )
            
            result = json.loads(response.text)
            
            # המרה למודלים
            weaknesses = [Weakness(**w) for w in result.get("weaknesses", [])]
            missing_params = [MissingParameter(**p) for p in result.get("missing_params", [])]
            pro_tips = [ProTip(**t) for t in result.get("pro_tips", [])]
            
            return CritiqueResult(
                weaknesses=weaknesses,
                missing_params=missing_params,
                pro_tips=pro_tips,
                overall_score=result.get("overall_score", 5),
                is_ready=result.get("is_ready", False)
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse critique response: {e}")
            # fallback - החזר תוצאה בסיסית
            return CritiqueResult(
                weaknesses=[Weakness(
                    type="unknown",
                    description="לא הצלחתי לנתח את הפרומפט",
                    suggestion="נסה שוב",
                    severity="medium"
                )],
                overall_score=5,
                is_ready=False
            )
        except Exception as e:
            logger.error(f"Critique failed: {e}")
            raise

    async def quick_score(self, prompt: str) -> int:
        """
        ציון מהיר לפרומפט (1-10) בלי ניתוח מלא.
        שימושי להשוואה לפני/אחרי שיפור.
        """
        score_prompt = f"""[ציון מהיר]
דרג את הפרומפט הבא מ-1 עד 10 לפי:
- בהירות (clarity)
- ספציפיות (specificity)  
- שלמות (completeness)

פרומפט: "{prompt}"

החזר רק מספר בין 1 ל-10, ללא הסברים."""

        try:
            response = await self.model.generate_content_async(
                score_prompt,
                generation_config={"temperature": 0.1}
            )
            score = int(response.text.strip())
            return max(1, min(10, score))
        except:
            return 5  # fallback

    def format_critique_hebrew(self, critique: CritiqueResult) -> str:
        """
        מעצב את הביקורת לתצוגה יפה בעברית (לטלגרם).
        """
        lines = []
        
        # ציון כללי
        score_emoji = "🟢" if critique.overall_score >= 7 else "🟡" if critique.overall_score >= 5 else "🔴"
        lines.append(f"{score_emoji} **ציון כללי: {critique.overall_score}/10**\n")
        
        # סטטוס
        if critique.is_ready:
            lines.append("✅ הפרומפט מוכן לשימוש!\n")
        else:
            lines.append("⚠️ מומלץ לשפר את הפרומפט\n")
        
        # נקודות חולשה (אם יש)
        if critique.weaknesses:
            lines.append("**🔍 נקודות לתיקון:**\n")
            for i, w in enumerate(critique.weaknesses, 1):
                severity_icon = "🔴" if w.severity == "high" else "🟡" if w.severity == "medium" else "⚪"
                lines.append(f"{i}. {severity_icon} **{w.type}**")
                lines.append(f"   {w.description}")
                lines.append(f"   💡 *{w.suggestion}*\n")
        
        # טיפים מקצועיים לשדרוג (החלק החשוב!)
        if critique.pro_tips:
            lines.append("**🚀 רעיונות לשדרוג הפרומפט:**\n")
            
            technique_icons = {
                "role_playing": "🎭",
                "chain_of_thought": "🔗",
                "few_shot": "📝",
                "constraints": "🎯",
                "structure": "📐",
                "creativity": "💡"
            }
            
            for i, tip in enumerate(critique.pro_tips, 1):
                icon = technique_icons.get(tip.technique, "💡")
                impact_stars = "⭐⭐⭐" if tip.impact == "high" else "⭐⭐" if tip.impact == "medium" else "⭐"
                
                lines.append(f"{i}. {icon} **{tip.title}** {impact_stars}")
                lines.append(f"   {tip.suggestion}")
                if tip.example:
                    lines.append(f"   📌 _דוגמה: \"{tip.example}\"_\n")
                else:
                    lines.append("")
        
        # פרמטרים חסרים (בסוף, פחות חשוב)
        if critique.missing_params:
            lines.append("**❓ שאלות להשלמה:**\n")
            for p in critique.missing_params:
                importance_icon = "❗" if p.importance == "required" else "💭"
                lines.append(f"{importance_icon} {p.question}")
        
        return "\n".join(lines)
