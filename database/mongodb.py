"""
MongoDB Connection and Operations
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import DESCENDING

from config import config
from core.models import PromptHistory, PromptCategory, UserSession

logger = logging.getLogger(__name__)


class MongoDB:
    """
    חיבור ל-MongoDB עם Motor (async driver).
    """
    
    _client: Optional[AsyncIOMotorClient] = None
    _db = None
    
    def __init__(self):
        if MongoDB._client is None:
            MongoDB._client = AsyncIOMotorClient(config.MONGODB_URI)
            MongoDB._db = MongoDB._client[config.MONGODB_DB_NAME]
            logger.info(f"Connected to MongoDB: {config.MONGODB_DB_NAME}")
    
    @property
    def db(self):
        return MongoDB._db
    
    @property
    def prompts_collection(self):
        return self.db["prompt_history"]
    
    @property
    def sessions_collection(self):
        return self.db["user_sessions"]
    
    @property
    def feedback_collection(self):
        return self.db["user_feedback"]
    
    # ========== Prompt History ==========
    
    async def save_prompt_history(self, history: PromptHistory) -> str:
        """שמירת היסטוריית פרומפט"""
        doc = history.model_dump()
        doc["category"] = doc["category"].value  # המרה ל-string
        
        result = await self.prompts_collection.insert_one(doc)
        logger.debug(f"Saved prompt history: {result.inserted_id}")
        return str(result.inserted_id)
    
    async def get_user_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """מחזיר היסטוריית פרומפטים של משתמש"""
        cursor = self.prompts_collection.find(
            {"user_id": user_id}
        ).sort("created_at", DESCENDING).limit(limit)
        
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        
        return results
    
    async def get_top_improvements(
        self,
        category: Optional[PromptCategory] = None,
        min_improvement: int = 3,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        מחזיר פרומפטים עם השיפור הגדול ביותר.
        שימושי לדוגמאות קהילתיות.
        """
        query = {}
        if category:
            query["category"] = category.value
        
        # חיפוש פרומפטים עם שיפור משמעותי בציון
        pipeline = [
            {"$match": query},
            {"$addFields": {
                "improvement": {"$subtract": ["$score_after", "$score_before"]}
            }},
            {"$match": {"improvement": {"$gte": min_improvement}}},
            {"$sort": {"improvement": -1, "score_after": -1}},
            {"$limit": limit},
            {"$project": {
                "original_prompt": 1,
                "improved_prompt": 1,
                "category": 1,
                "score_before": 1,
                "score_after": 1,
                "improvement": 1
            }}
        ]
        
        results = []
        async for doc in self.prompts_collection.aggregate(pipeline):
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        
        return results
    
    async def add_feedback(
        self,
        prompt_id: str,
        user_id: str,
        rating: int,
        feedback_text: Optional[str] = None
    ):
        """הוספת משוב על שיפור"""
        from bson import ObjectId
        
        await self.prompts_collection.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": {
                "rating": rating,
                "feedback": feedback_text,
                "feedback_at": datetime.utcnow()
            }}
        )
        
        # שמירת משוב נפרד לניתוח
        await self.feedback_collection.insert_one({
            "prompt_id": prompt_id,
            "user_id": user_id,
            "rating": rating,
            "feedback_text": feedback_text,
            "created_at": datetime.utcnow()
        })
    
    # ========== User Sessions ==========
    
    async def get_session(self, user_id: str) -> Optional[UserSession]:
        """מחזיר סשן משתמש"""
        doc = await self.sessions_collection.find_one({"user_id": user_id})
        if doc:
            doc.pop("_id", None)
            return UserSession(**doc)
        return None
    
    async def save_session(self, session: UserSession):
        """שמירת/עדכון סשן"""
        doc = session.model_dump()
        await self.sessions_collection.update_one(
            {"user_id": session.user_id},
            {"$set": doc},
            upsert=True
        )
    
    async def clear_session(self, user_id: str):
        """מחיקת סשן"""
        await self.sessions_collection.delete_one({"user_id": user_id})
    
    # ========== Statistics ==========
    
    async def get_stats(self) -> Dict[str, Any]:
        """סטטיסטיקות כלליות"""
        total_prompts = await self.prompts_collection.count_documents({})
        
        # ממוצע שיפור
        pipeline = [
            {"$addFields": {
                "improvement": {"$subtract": ["$score_after", "$score_before"]}
            }},
            {"$group": {
                "_id": None,
                "avg_improvement": {"$avg": "$improvement"},
                "avg_score_before": {"$avg": "$score_before"},
                "avg_score_after": {"$avg": "$score_after"}
            }}
        ]
        
        stats_result = await self.prompts_collection.aggregate(pipeline).to_list(1)
        
        # חלוקה לפי קטגוריות
        category_pipeline = [
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1}
            }}
        ]
        categories = await self.prompts_collection.aggregate(category_pipeline).to_list(None)
        
        return {
            "total_prompts": total_prompts,
            "averages": stats_result[0] if stats_result else {},
            "by_category": {c["_id"]: c["count"] for c in categories}
        }
    
    # ========== Indexes ==========
    
    async def ensure_indexes(self):
        """יצירת אינדקסים נדרשים"""
        # אינדקס על user_id
        await self.prompts_collection.create_index("user_id")
        
        # אינדקס על קטגוריה
        await self.prompts_collection.create_index("category")
        
        # אינדקס על תאריך
        await self.prompts_collection.create_index([("created_at", DESCENDING)])
        
        # אינדקס משולב לחיפוש דוגמאות טובות
        await self.prompts_collection.create_index([
            ("category", 1),
            ("score_after", DESCENDING)
        ])
        
        logger.info("MongoDB indexes created")
