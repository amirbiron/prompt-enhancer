"""
Refiner Agent
סוכן שמשפר פרומפטים על בסיס הביקורת
"""
import json
import logging
from typing import Optional, List
import google.generativeai as genai

from config import config
from core.models import PromptCategory, CritiqueResult, Weakness, MissingParameter

logger = logging.getLogger(__name__)


class PromptRefiner:
    """
    סוכן שמשפר פרומפטים על בסיס:
    - נקודות חולשה שזוהו
    - פרמטרים חסרים
    - best practices לקטגוריה
    
    משתמש במודל איכותי יותר (Gemini Pro) כי זה השלב הקריטי.
    """
    
    def __init__(self):
        genai.configure(api_key=config.GEMINI_API_KEY)
        # מודל איכותי יותר לשיפור
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    async def refine(
        self,
        original_prompt: str,
        category: PromptCategory,
        critique: CritiqueResult,
        user_answers: Optional[dict] = None
    ) -> str:
        """
        משפר פרומפט על בסיס הביקורת.
        
        Args:
            original_prompt: הפרומפט המקורי
            category: הקטגוריה שזוהתה
            critique: תוצאת הביקורת
            user_answers: תשובות המשתמש לשאלות (אופציונלי)
            
        Returns:
            הפרומפט המשופר
        """
        # בניית הקשר מהביקורת
        weaknesses_text = self._format_weaknesses(critique.weaknesses)
        missing_params_text = self._format_missing_params(critique.missing_params)
        user_answers_text = self._format_user_answers(user_answers) if user_answers else ""
        
        refinement_prompt = f"""[מצב שיפור פרומפט - עברית]

פרומפט מקורי:
"{original_prompt}"

קטגוריה: {category.value}
ציון נוכחי: {critique.overall_score}/10

נקודות חולשה שזוהו:
{weaknesses_text}

פרמטרים חסרים:
{missing_params_text}

{user_answers_text}

צור פרומפט משופר שעונה על הדרישות הבאות:

1. **מטפל בכל נקודות החולשה** - כל בעיה שזוהתה צריכה להיות מטופלת
2. **משלים פרמטרים חסרים** - הוסף את המידע החסר בצורה טבעית
3. **שומר על הכוונה המקורית** - אל תשנה את המטרה של המשתמש
4. **כולל דוגמאות קונקרטיות** - אם רלוונטי לקטגוריה
5. **מובנה ומאורגן** - עם מבנה ברור (רקע, משימה, פורמט פלט)
6. **בעברית טבעית** - שפה ברורה וזורמת

פורמט מומלץ לפרומפט משופר:
```
[רקע/הקשר - אם רלוונטי]
[המשימה העיקרית]
[פרטים ספציפיים: קלט, פלט, מגבלות]
[דוגמאות - אם רלוונטי]
```

החזר רק את הפרומפט המשופר, ללא הסברים או הערות נוספות."""

        try:
            response = await self.model.generate_content_async(
                refinement_prompt,
                generation_config={
                    "temperature": 0.4,  # מאוזן - לא יצירתי מדי, לא נוקשה מדי
                    "max_output_tokens": 1000
                }
            )
            
            improved = response.text.strip()
            
            # נקה סימני קוד אם יש
            improved = improved.strip('`').strip()
            if improved.startswith('text\n'):
                improved = improved[5:]
            
            return improved
            
        except Exception as e:
            logger.error(f"Refinement failed: {e}")
            raise
    
    async def refine_iterative(
        self,
        original_prompt: str,
        category: PromptCategory,
        max_iterations: int = 3,
        target_score: int = 8
    ) -> tuple[str, int, List[CritiqueResult]]:
        """
        שיפור איטרטיבי - ממשיך לשפר עד שמגיעים לציון יעד.
        
        Args:
            original_prompt: הפרומפט המקורי
            category: הקטגוריה
            max_iterations: מקסימום איטרציות
            target_score: ציון יעד (עוצר כשמגיעים)
            
        Returns:
            tuple של (פרומפט משופר, מספר איטרציות, היסטוריית ביקורות)
        """
        from agents.shadow_critic import ShadowCritic
        critic = ShadowCritic()
        
        current_prompt = original_prompt
        critiques_history = []
        
        for iteration in range(max_iterations):
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")
            
            # ביקורת
            critique = await critic.critique(current_prompt, category)
            critiques_history.append(critique)
            
            logger.info(f"Score: {critique.overall_score}/10")
            
            # בדיקה אם הגענו ליעד
            if critique.overall_score >= target_score or critique.is_ready:
                logger.info(f"Target reached at iteration {iteration + 1}")
                return current_prompt, iteration + 1, critiques_history
            
            # שיפור
            current_prompt = await self.refine(
                original_prompt=current_prompt,
                category=category,
                critique=critique
            )
        
        return current_prompt, max_iterations, critiques_history
    
    def _format_weaknesses(self, weaknesses: List[Weakness]) -> str:
        """מעצב נקודות חולשה לטקסט"""
        if not weaknesses:
            return "לא זוהו נקודות חולשה משמעותיות"
        
        lines = []
        for i, w in enumerate(weaknesses, 1):
            lines.append(f"{i}. [{w.type}] {w.description}")
            lines.append(f"   הצעה: {w.suggestion}")
        return "\n".join(lines)
    
    def _format_missing_params(self, params: List[MissingParameter]) -> str:
        """מעצב פרמטרים חסרים לטקסט"""
        if not params:
            return "לא זוהו פרמטרים חסרים קריטיים"
        
        lines = []
        for p in params:
            importance = "חובה" if p.importance == "required" else "מומלץ"
            lines.append(f"- {p.name} ({importance}): {p.question}")
        return "\n".join(lines)
    
    def _format_user_answers(self, answers: dict) -> str:
        """מעצב תשובות המשתמש"""
        if not answers:
            return ""
        
        lines = ["תשובות המשתמש:"]
        for key, value in answers.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    async def generate_explanation(
        self,
        original_prompt: str,
        improved_prompt: str,
        weaknesses: List[Weakness]
    ) -> str:
        """
        מייצר הסבר בעברית על השיפורים שנעשו.
        """
        explanation_prompt = f"""[הסבר שיפורים - עברית]

פרומפט מקורי:
"{original_prompt}"

פרומפט משופר:
"{improved_prompt}"

נקודות חולשה שטופלו:
{self._format_weaknesses(weaknesses)}

כתוב הסבר קצר (3-5 משפטים) בעברית שמסביר:
1. מה היו הבעיות העיקריות
2. איך הפרומפט המשופר מטפל בהן
3. למה זה ישפר את התוצאות

שמור על טון ידידותי ומעודד. אל תהיה ביקורתי מדי."""

        try:
            response = await self.model.generate_content_async(
                explanation_prompt,
                generation_config={
                    "temperature": 0.5,
                    "max_output_tokens": 300
                }
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return "הפרומפט שופר על ידי הוספת פרטים חסרים והבהרת המטרה."
