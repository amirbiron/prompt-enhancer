"""
Telegram Bot for Prompt Enhancer
בוט טלגרם לשיפור פרומפטים בעברית
"""
import logging
import asyncio
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from config import config
from core.orchestrator import orchestrator
from core.models import UserSession
from database.mongodb import MongoDB

logger = logging.getLogger(__name__)

# ========== Handlers ==========

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /start"""
    logger.info(f"start_command called by user {update.effective_user.id}")
    welcome_message = """🚀 **ברוכים הבאים ל-Prompt Enhancer!**

אני עוזר לך לשפר פרומפטים ל-AI בעברית.

**איך זה עובד:**
1️⃣ שלח לי פרומפט
2️⃣ אנתח אותו ואראה לך נקודות חולשה
3️⃣ אציע פרומפט משופר

**פקודות זמינות:**
/analyze - ניתוח בלבד (בלי שיפור אוטומטי)
/improve - שיפור מלא עם הסבר
/history - היסטוריית הפרומפטים שלך
/examples - דוגמאות לשיפורים טובים
/help - עזרה

**התחל עכשיו - פשוט שלח פרומפט!** ✨"""

    try:
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("start_command reply sent successfully")
    except Exception as e:
        logger.error(f"start_command failed to send reply: {e}", exc_info=True)
        # נסה בלי markdown אם יש בעיה
        await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /help"""
    help_text = """📖 **מדריך שימוש**

**מצב ברירת מחדל - ניתוח:**
פשוט שלח פרומפט ואקבל:
• ציון 1-10
• נקודות חולשה
• שאלות להשלמה

**מצב שיפור מלא:**
כתוב `/improve` לפני הפרומפט או לחץ על "שפר אוטומטית"

**טיפים לפרומפטים טובים:**
✅ היה ספציפי - מה בדיוק אתה רוצה?
✅ הגדר פורמט פלט - איך התוצאה צריכה להיראות?
✅ תן הקשר - למה אתה צריך את זה?
✅ הוסף דוגמאות - אם רלוונטי

**דוגמה לפרומפט חלש:**
❌ "כתוב לי קוד לאתר"

**דוגמה לפרומפט חזק:**
✅ "כתוב קוד Python Flask לאתר portfolio עם 3 עמודים: בית, אודות, צור קשר. השתמש ב-Bootstrap 5 לעיצוב. הקוד צריך לכלול תיקיית templates."

**משוב:**
לאחר כל שיפור, דרג את התוצאה 1-5 ⭐"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /analyze - ניתוח בלבד"""
    # בדיקה אם יש טקסט אחרי הפקודה
    if context.args:
        prompt = " ".join(context.args)
        await analyze_prompt(update, context, prompt)
    else:
        # שמירת מצב - מחכים לפרומפט
        db = MongoDB()
        session = UserSession(
            user_id=str(update.effective_user.id),
            awaiting_response="analyze"
        )
        await db.save_session(session)
        
        await update.message.reply_text(
            "📝 שלח את הפרומפט שאתה רוצה לנתח:"
        )


async def improve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /improve - שיפור מלא"""
    if context.args:
        prompt = " ".join(context.args)
        await improve_prompt(update, context, prompt)
    else:
        db = MongoDB()
        session = UserSession(
            user_id=str(update.effective_user.id),
            awaiting_response="improve"
        )
        await db.save_session(session)
        
        await update.message.reply_text(
            "📝 שלח את הפרומפט שאתה רוצה לשפר:"
        )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /history - היסטוריה"""
    user_id = str(update.effective_user.id)
    
    history = await orchestrator.get_user_history(user_id, limit=5)
    
    if not history:
        await update.message.reply_text(
            "📭 עדיין אין לך היסטוריית פרומפטים.\nשלח פרומפט כדי להתחיל!"
        )
        return
    
    response = "📜 **5 הפרומפטים האחרונים שלך:**\n\n"
    
    for i, item in enumerate(history, 1):
        original = item["original_prompt"][:50] + "..." if len(item["original_prompt"]) > 50 else item["original_prompt"]
        score_change = f"{item['score_before']}→{item['score_after']}"
        
        response += f"{i}. {original}\n"
        response += f"   📊 ציון: {score_change}\n\n"
    
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def examples_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /examples - דוגמאות קהילתיות"""
    examples = await orchestrator.get_community_examples(min_improvement=3, limit=3)
    
    if not examples:
        await update.message.reply_text(
            "📭 עדיין אין מספיק דוגמאות.\nהמשך לשפר פרומפטים וזה ישתנה!"
        )
        return
    
    response = "🌟 **דוגמאות לשיפורים מוצלחים:**\n\n"
    
    for i, ex in enumerate(examples, 1):
        response += f"**{i}. קטגוריה: {ex['category']}**\n"
        response += f"📊 שיפור: {ex['score_before']}→{ex['score_after']} (+{ex['improvement']})\n\n"
        
        original = ex["original_prompt"][:100] + "..." if len(ex["original_prompt"]) > 100 else ex["original_prompt"]
        improved = ex["improved_prompt"][:150] + "..." if len(ex["improved_prompt"]) > 150 else ex["improved_prompt"]
        
        response += f"❌ לפני:\n`{original}`\n\n"
        response += f"✅ אחרי:\n`{improved}`\n\n"
        response += "---\n\n"
    
    await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בהודעות טקסט רגילות"""
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    # בדיקה אם יש סשן פעיל
    db = MongoDB()
    session = await db.get_session(user_id)
    
    if session and session.awaiting_response == "improve":
        # מצב שיפור
        await db.clear_session(user_id)
        await improve_prompt(update, context, text)
    else:
        # ברירת מחדל - ניתוח
        await analyze_prompt(update, context, text)


async def analyze_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    """ביצוע ניתוח פרומפט"""
    user_id = str(update.effective_user.id)
    
    # הודעת המתנה
    waiting_msg = await update.message.reply_text("🔍 מנתח את הפרומפט...")
    waiting_msg_deleted = False
    
    try:
        # ניתוח
        analysis = await orchestrator.analyze_prompt(prompt, user_id)
        
        # בניית תגובה
        response = f"**{analysis['category_description']}**\n\n"
        response += analysis['formatted_critique']
        
        # כפתורים
        keyboard = [
            [InlineKeyboardButton("✨ שפר אוטומטית", callback_data=f"improve:{user_id}")],
            [InlineKeyboardButton("📝 שאל שאלות", callback_data=f"questions:{user_id}")]
        ]
        
        if analysis['questions']:
            questions_text = "\n".join(analysis['questions'])
            response += f"\n\n**❓ שאלות מומלצות:**\n{questions_text}"
        
        # שמירת הפרומפט בסשן לשימוש עתידי
        db = MongoDB()
        session = UserSession(
            user_id=user_id,
            current_prompt=prompt,
            current_category=analysis['category'],
            context={"analysis": analysis}
        )
        await db.save_session(session)
        
        # מחיקת הודעת המתנה רק אחרי שהכל הצליח
        try:
            await waiting_msg.delete()
            waiting_msg_deleted = True
        except Exception:
            pass  # אם המחיקה נכשלה, נמשיך בכל זאת
        
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        error_text = "❌ שגיאה בניתוח. נסה שוב או שלח פרומפט אחר."
        if waiting_msg_deleted:
            # ההודעה נמחקה, שולחים הודעה חדשה
            await update.message.reply_text(error_text)
        else:
            # ההודעה עדיין קיימת, מעדכנים אותה
            try:
                await waiting_msg.edit_text(error_text)
            except Exception:
                # אם גם העריכה נכשלה, שולחים הודעה חדשה
                await update.message.reply_text(error_text)


async def improve_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt: str):
    """ביצוע שיפור מלא"""
    user_id = str(update.effective_user.id)
    
    # הודעת המתנה
    waiting_msg = await update.message.reply_text(
        "⏳ משפר את הפרומפט...\nזה עשוי לקחת כמה שניות."
    )
    waiting_msg_deleted = False
    
    try:
        # שיפור
        result = await orchestrator.refine_prompt(
            prompt=prompt,
            user_id=user_id,
            use_iterations=True
        )
        
        # בניית תגובה
        score_emoji = "🟢" if result.critique.overall_score >= 7 else "🟡"
        delta_emoji = "📈" if result.improvement_delta > 0 else "➡️"
        
        response = f"✨ **פרומפט משופר!**\n\n"
        response += f"📊 ציון: {result.critique.overall_score}/10 {score_emoji}\n"
        response += f"{delta_emoji} שיפור: +{result.improvement_delta} נקודות\n"
        response += f"🔄 איטרציות: {result.iterations_used}\n\n"
        response += f"**📝 הפרומפט המשופר:**\n```\n{result.improved_prompt}\n```\n\n"
        response += f"**💡 הסבר:**\n{result.explanation}"
        
        # כפתורי משוב
        keyboard = [
            [
                InlineKeyboardButton("⭐1", callback_data=f"rate:1:{user_id}"),
                InlineKeyboardButton("⭐2", callback_data=f"rate:2:{user_id}"),
                InlineKeyboardButton("⭐3", callback_data=f"rate:3:{user_id}"),
                InlineKeyboardButton("⭐4", callback_data=f"rate:4:{user_id}"),
                InlineKeyboardButton("⭐5", callback_data=f"rate:5:{user_id}"),
            ],
            [InlineKeyboardButton("📋 העתק", callback_data=f"copy:{user_id}")]
        ]
        
        # מחיקת הודעת המתנה רק אחרי שהכל הצליח
        try:
            await waiting_msg.delete()
            waiting_msg_deleted = True
        except Exception:
            pass  # אם המחיקה נכשלה, נמשיך בכל זאת
        
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"Improvement failed: {e}")
        error_text = "❌ שגיאה בשיפור. נסה שוב או שלח פרומפט אחר."
        if waiting_msg_deleted:
            # ההודעה נמחקה, שולחים הודעה חדשה
            await update.message.reply_text(error_text)
        else:
            # ההודעה עדיין קיימת, מעדכנים אותה
            try:
                await waiting_msg.edit_text(error_text)
            except Exception:
                # אם גם העריכה נכשלה, שולחים הודעה חדשה
                await update.message.reply_text(error_text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בלחיצות על כפתורים"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    action = data[0]
    
    if action == "improve":
        user_id = data[1]
        db = MongoDB()
        session = await db.get_session(user_id)
        
        if session and session.current_prompt:
            # יצירת הודעה "מזויפת" לשיפור
            await query.message.reply_text(
                "⏳ משפר את הפרומפט...\nזה עשוי לקחת כמה שניות."
            )
            
            result = await orchestrator.refine_prompt(
                prompt=session.current_prompt,
                user_id=user_id,
                use_iterations=True
            )
            
            response = f"✨ **פרומפט משופר!**\n\n"
            response += f"**📝 הפרומפט המשופר:**\n```\n{result.improved_prompt}\n```\n\n"
            response += f"**💡 הסבר:**\n{result.explanation}"
            
            await query.message.reply_text(
                response,
                parse_mode=ParseMode.MARKDOWN
            )
    
    elif action == "rate":
        rating = int(data[1])
        user_id = data[2]
        
        # TODO: שמירת הדירוג
        await query.message.reply_text(
            f"🙏 תודה על הדירוג! ({rating}/5 ⭐)"
        )
    
    elif action == "questions":
        user_id = data[1]
        db = MongoDB()
        session = await db.get_session(user_id)
        
        if session and session.context.get("analysis"):
            questions = session.context["analysis"].get("questions", [])
            if questions:
                await query.message.reply_text(
                    "📝 ענה על השאלות הבאות ושלח את התשובות:\n\n" + 
                    "\n".join(questions)
                )


# ========== Bot Setup ==========

def create_bot() -> Application:
    """יצירת הבוט"""
    logger.info("Creating bot application...")
    print("Creating bot application...")  # Debug print
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # פקודות
    application.add_handler(CommandHandler("start", start_command))
    logger.info("Added start command handler")
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("improve", improve_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("examples", examples_command))
    
    # הודעות טקסט
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Callbacks
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    return application


async def setup_webhook(application: Application, webhook_url: str):
    """הגדרת webhook"""
    await application.bot.set_webhook(
        url=f"{webhook_url}/webhook",
        allowed_updates=["message", "callback_query"]
    )
    logger.info(f"Webhook set to {webhook_url}/webhook")


def run_polling():
    """הרצה במצב polling (לפיתוח)"""
    application = create_bot()
    logger.info("Starting bot in polling mode...")
    application.run_polling(allowed_updates=["message", "callback_query"])
