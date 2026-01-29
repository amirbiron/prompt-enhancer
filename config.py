"""
Prompt Enhancer - Configuration
מערכת שיפור פרומפטים עם סוכני AI
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "prompt_enhancer")
    
    # AI Models
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Model Selection
    PRIMARY_MODEL: str = os.getenv("PRIMARY_MODEL", "gemini")  # gemini, claude, openai
    CRITIC_MODEL: str = os.getenv("CRITIC_MODEL", "gemini-flash")  # מודל זול לביקורת
    REFINER_MODEL: str = os.getenv("REFINER_MODEL", "gemini-pro")  # מודל איכותי לשיפור
    
    # App Settings
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", "3"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    
    # Webhook (for Render)
    WEBHOOK_URL: Optional[str] = os.getenv("WEBHOOK_URL")  # https://your-app.onrender.com

config = Config()
