"""
Prompt Refinement Orchestrator
מנהל הזרימה המרכזי של מערכת שיפור הפרומפטים
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from config import config
from core.models import (
    PromptCategory, CritiqueResult, RefinementResult, 
    PromptHistory, MissingParameter
)
from agents import ShadowCritic, CategoryRouter, ParameterValidator, PromptRefiner
from database.mongodb import MongoDB

logger = logging.getLogger(__name__)


class PromptEnhancerOrchestrator:
    """
    מנהל זרימה מרכזי למערכת שיפור פרומפטים.
    
    זרימת עבודה:
    1. זיהוי קטגוריה
    2. בדיקת פרמטרים חסרים
    3. ביקורת (Shadow Critic)
    4. שיפור איטרטיבי
    5. שמירה למסד נתונים
    """
    
    def __init__(self):
        self.category_router = CategoryRouter()
        self.param_validator = ParameterValidator()
        self.shadow_critic = ShadowCritic()
        self.refiner = PromptRefiner()
        self.db = MongoDB()
    
    async def analyze_prompt(
        self, 
        prompt: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        שלב ראשון: ניתוח פרומפט בלי שיפור.
        מחזיר את הביקורת והשאלות לפני שיפור אוטומטי.
        
        מתאים ל"מצב מאמן" - לתת למשתמש לראות מה צריך לשפר.
        """
        logger.info(f"Analyzing prompt for user {user_id}")
        
        # זיהוי קטגוריה
        category, confidence = await self.category_router.detect_category(prompt)
        logger.info(f"Category: {category.value} (confidence: {confidence:.2f})")
        
        # ביקורת
        critique = await self.shadow_critic.critique(prompt, category)
        
        # בדיקת פרמטרים חסרים
        missing_params = await self.param_validator.validate(prompt, category)
        
        # הוספת פרמטרים חסרים לביקורת
        critique.missing_params = missing_params
        
        # שאלות למשתמש
        questions = self.param_validator.get_questions_for_missing(missing_params)
        
        return {
            "original_prompt": prompt,
            "category": category,
            "category_description": self.category_router.get_category_description(category),
            "confidence": confidence,
            "critique": critique,
            "questions": questions,
            "formatted_critique": self.shadow_critic.format_critique_hebrew(critique)
        }
    
    async def refine_prompt(
        self,
        prompt: str,
        user_id: str,
        user_answers: Optional[Dict[str, str]] = None,
        use_iterations: bool = True,
        max_iterations: int = None
    ) -> RefinementResult:
        """
        שלב שני: שיפור מלא של הפרומפט.
        
        Args:
            prompt: הפרומפט לשיפור
            user_id: מזהה המשתמש
            user_answers: תשובות לשאלות שנשאלו (אופציונלי)
            use_iterations: האם להשתמש בשיפור איטרטיבי
            max_iterations: מקסימום איטרציות (ברירת מחדל מ-config)
        """
        logger.info(f"Refining prompt for user {user_id}")
        
        if max_iterations is None:
            max_iterations = config.MAX_ITERATIONS
        
        # שלב 1: ניתוח ראשוני
        analysis = await self.analyze_prompt(prompt, user_id)
        category = analysis["category"]
        initial_critique = analysis["critique"]
        
        # ציון התחלתי
        score_before = initial_critique.overall_score
        
        # שלב 2: שיפור
        if use_iterations and max_iterations > 1:
            # שיפור איטרטיבי
            improved_prompt, iterations_used, critiques = await self.refiner.refine_iterative(
                original_prompt=prompt,
                category=category,
                max_iterations=max_iterations,
                target_score=8
            )
            final_critique = critiques[-1] if critiques else initial_critique
        else:
            # שיפור חד-פעמי
            improved_prompt = await self.refiner.refine(
                original_prompt=prompt,
                category=category,
                critique=initial_critique,
                user_answers=user_answers
            )
            iterations_used = 1
            # ביקורת סופית
            final_critique = await self.shadow_critic.critique(improved_prompt, category)
        
        # ציון סופי
        score_after = final_critique.overall_score
        
        # הסבר לשיפורים
        explanation = await self.refiner.generate_explanation(
            original_prompt=prompt,
            improved_prompt=improved_prompt,
            weaknesses=initial_critique.weaknesses
        )
        
        # שלב 3: שמירה למסד נתונים
        await self._save_to_db(
            user_id=user_id,
            original=prompt,
            improved=improved_prompt,
            category=category,
            critique=initial_critique,
            score_before=score_before,
            score_after=score_after,
            iterations=iterations_used
        )
        
        return RefinementResult(
            original_prompt=prompt,
            improved_prompt=improved_prompt,
            category=category,
            critique=final_critique,
            iterations_used=iterations_used,
            explanation=explanation,
            improvement_delta=score_after - score_before
        )
    
    async def quick_critique(self, prompt: str) -> str:
        """
        ביקורת מהירה - מחזיר רק טקסט מעוצב לתצוגה.
        שימושי לתגובה מהירה בטלגרם.
        """
        # זיהוי קטגוריה
        category, _ = await self.category_router.detect_category(prompt)
        
        # ביקורת
        critique = await self.shadow_critic.critique(prompt, category)
        
        # עיצוב לתצוגה
        return self.shadow_critic.format_critique_hebrew(critique)
    
    async def _save_to_db(
        self,
        user_id: str,
        original: str,
        improved: str,
        category: PromptCategory,
        critique: CritiqueResult,
        score_before: int,
        score_after: int,
        iterations: int
    ):
        """שמירה למסד נתונים"""
        try:
            history = PromptHistory(
                user_id=user_id,
                original_prompt=original,
                improved_prompt=improved,
                category=category,
                weaknesses=[w.model_dump() for w in critique.weaknesses],
                score_before=score_before,
                score_after=score_after,
                iterations=iterations
            )
            
            await self.db.save_prompt_history(history)
            logger.info(f"Saved prompt history for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to save to DB: {e}")
            # לא נכשל את כל הזרימה בגלל שמירה
    
    async def get_user_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> list:
        """מחזיר היסטוריית פרומפטים של משתמש"""
        return await self.db.get_user_history(user_id, limit)
    
    async def get_community_examples(
        self,
        category: Optional[PromptCategory] = None,
        min_improvement: int = 3,
        limit: int = 5
    ) -> list:
        """
        מחזיר דוגמאות קהילתיות טובות.
        שימושי להראות למשתמשים איך נראה שיפור טוב.
        """
        return await self.db.get_top_improvements(
            category=category,
            min_improvement=min_improvement,
            limit=limit
        )


# Singleton instance
orchestrator = PromptEnhancerOrchestrator()
