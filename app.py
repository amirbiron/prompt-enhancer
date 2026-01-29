"""
Prompt Enhancer - Main Application
Flask app with Telegram webhook and Web API
"""
import asyncio
import logging
import threading
from flask import Flask, request, jsonify, render_template
from telegram import Update

from config import config
from bot import create_bot, setup_webhook
from core.orchestrator import orchestrator
from database.mongodb import MongoDB

# ========== Logging Setup ==========
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== Flask App ==========
app = Flask(__name__)

# Global bot application
bot_app = None
bot_initialized = False

# ========== Persistent Event Loop ==========
# Event loop קבוע שרץ ברקע - פותר את בעיית "Event loop is closed"
_loop = None
_loop_thread = None


def get_event_loop():
    """קבלת event loop קבוע שרץ ברקע"""
    global _loop, _loop_thread
    
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
        _loop_thread.start()
        logger.info("Created new persistent event loop")
    
    return _loop


def run_async(coro):
    """הרצת coroutine על ה-event loop הקבוע"""
    loop = get_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)  # timeout של 2 דקות


async def initialize_bot():
    """Initialize bot application for webhook mode"""
    global bot_app, bot_initialized
    if bot_app is None:
        bot_app = create_bot()
    if not bot_initialized:
        await bot_app.initialize()
        bot_initialized = True
    return bot_app


def get_bot():
    """Lazy initialization of bot"""
    global bot_app
    if bot_app is None:
        bot_app = create_bot()
    return bot_app


# ========== Health Check ==========
@app.route("/")
def index():
    """דף בית / בדיקת תקינות"""
    return render_template("index.html")


@app.route("/health")
def health():
    """Health check לפנקי מערכות ניטור ו-Render"""
    return jsonify({
        "status": "healthy",
        "service": "prompt-enhancer",
        "version": "1.0.0"
    })


# ========== Telegram Webhook ==========
@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    """Webhook endpoint לטלגרם"""
    print("=== WEBHOOK RECEIVED ===", flush=True)
    logger.info("Webhook received")
    try:
        data = request.get_json()
        print(f"=== WEBHOOK DATA: {data} ===", flush=True)
        logger.info(f"Webhook data: {data}")

        async def process():
            print("=== STARTING ASYNC PROCESS ===", flush=True)
            logger.info("Starting async process")
            bot = await initialize_bot()
            print("=== BOT INITIALIZED ===", flush=True)
            logger.info("Bot initialized")
            update = Update.de_json(data, bot.bot)
            print(f"=== UPDATE PARSED: {update} ===", flush=True)
            logger.info(f"Update parsed: {update}")
            await bot.process_update(update)
            print("=== UPDATE PROCESSED ===", flush=True)
            logger.info("Update processed")

        # שימוש ב-event loop קבוע במקום asyncio.run() שסוגר את ה-loop
        run_async(process())

        print("=== WEBHOOK COMPLETED ===", flush=True)
        logger.info("Webhook completed successfully")
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"=== WEBHOOK ERROR: {e} ===", flush=True)
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/set-webhook", methods=["POST"])
def set_webhook():
    """הגדרת webhook (להרצה חד-פעמית)"""
    if not config.WEBHOOK_URL:
        return jsonify({"error": "WEBHOOK_URL not configured"}), 400
    
    try:
        bot = get_bot()
        run_async(setup_webhook(bot, config.WEBHOOK_URL))
        return jsonify({"status": "webhook set", "url": config.WEBHOOK_URL})
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({"error": str(e)}), 500


# ========== REST API ==========
@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    API לניתוח פרומפט
    
    Request:
        {"prompt": "הפרומפט לניתוח", "user_id": "optional"}
    
    Response:
        {"category": "...", "critique": {...}, "questions": [...]}
    """
    data = request.get_json()
    
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field"}), 400
    
    prompt = data["prompt"]
    user_id = data.get("user_id", "api_user")
    
    try:
        result = run_async(orchestrator.analyze_prompt(prompt, user_id))
        
        # המרה לפורמט JSON-friendly
        return jsonify({
            "original_prompt": result["original_prompt"],
            "category": result["category"].value,
            "category_description": result["category_description"],
            "confidence": result["confidence"],
            "critique": {
                "weaknesses": [w.model_dump() for w in result["critique"].weaknesses],
                "missing_params": [p.model_dump() for p in result["critique"].missing_params],
                "overall_score": result["critique"].overall_score,
                "is_ready": result["critique"].is_ready
            },
            "questions": result["questions"],
            "formatted_critique": result["formatted_critique"]
        })
    except Exception as e:
        logger.error(f"API analyze error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/improve", methods=["POST"])
def api_improve():
    """
    API לשיפור פרומפט
    
    Request:
        {
            "prompt": "הפרומפט לשיפור",
            "user_id": "optional",
            "user_answers": {"param": "value"} (optional),
            "max_iterations": 3 (optional)
        }
    
    Response:
        {"original": "...", "improved": "...", "explanation": "...", ...}
    """
    data = request.get_json()
    
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field"}), 400
    
    prompt = data["prompt"]
    user_id = data.get("user_id", "api_user")
    user_answers = data.get("user_answers")
    max_iterations = data.get("max_iterations", config.MAX_ITERATIONS)
    
    try:
        result = run_async(orchestrator.refine_prompt(
            prompt=prompt,
            user_id=user_id,
            user_answers=user_answers,
            max_iterations=max_iterations
        ))
        
        return jsonify({
            "original_prompt": result.original_prompt,
            "improved_prompt": result.improved_prompt,
            "category": result.category.value,
            "score": result.critique.overall_score,
            "iterations_used": result.iterations_used,
            "improvement_delta": result.improvement_delta,
            "explanation": result.explanation,
            "critique": {
                "weaknesses": [w.model_dump() for w in result.critique.weaknesses],
                "overall_score": result.critique.overall_score,
                "is_ready": result.critique.is_ready
            }
        })
    except Exception as e:
        logger.error(f"API improve error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/quick-critique", methods=["POST"])
def api_quick_critique():
    """
    API לביקורת מהירה (טקסט בלבד)
    
    Request:
        {"prompt": "הפרומפט"}
    
    Response:
        {"critique": "טקסט מעוצב בעברית"}
    """
    data = request.get_json()
    
    if not data or "prompt" not in data:
        return jsonify({"error": "Missing 'prompt' field"}), 400
    
    try:
        critique = run_async(orchestrator.quick_critique(data["prompt"]))
        return jsonify({"critique": critique})
    except Exception as e:
        logger.error(f"API quick-critique error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """סטטיסטיקות המערכת"""
    try:
        db = MongoDB()
        stats = run_async(db.get_stats())
        return jsonify(stats)
    except Exception as e:
        logger.error(f"API stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/examples", methods=["GET"])
def api_examples():
    """דוגמאות קהילתיות"""
    try:
        category = request.args.get("category")
        limit = int(request.args.get("limit", 5))
        
        examples = run_async(orchestrator.get_community_examples(
            category=category,
            limit=limit
        ))
        return jsonify({"examples": examples})
    except Exception as e:
        logger.error(f"API examples error: {e}")
        return jsonify({"error": str(e)}), 500


# ========== Startup ==========
@app.before_request
def startup_tasks():
    """משימות הפעלה ראשונה - אינדקסים ו-webhook"""
    # יצירת אינדקסים
    if not hasattr(app, '_indexes_created'):
        try:
            db = MongoDB()
            run_async(db.ensure_indexes())
            app._indexes_created = True
            logger.info("Database indexes ensured")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    # רישום webhook
    if not hasattr(app, '_webhook_set') and config.WEBHOOK_URL:
        try:
            bot = get_bot()
            webhook_url = f"{config.WEBHOOK_URL}/webhook"
            run_async(bot.bot.set_webhook(url=webhook_url))
            app._webhook_set = True
            logger.info(f"Webhook registered: {webhook_url}")
            print(f"=== WEBHOOK REGISTERED: {webhook_url} ===", flush=True)
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}")
            print(f"=== WEBHOOK REGISTRATION FAILED: {e} ===", flush=True)


# ========== Main ==========
if __name__ == "__main__":
    # בדיקה אם להריץ במצב webhook או polling
    if config.WEBHOOK_URL:
        # Production mode with webhook
        logger.info(f"Starting in webhook mode on port {config.PORT}")
        app.run(host="0.0.0.0", port=config.PORT, debug=config.DEBUG)
    else:
        # Development mode with polling
        logger.info("Starting in polling mode (development)")
        from bot import run_polling
        
        # הרצת Flask ב-thread נפרד
        import threading
        flask_thread = threading.Thread(
            target=lambda: app.run(host="0.0.0.0", port=config.PORT, debug=False)
        )
        flask_thread.daemon = True
        flask_thread.start()
        
        # הרצת הבוט במצב polling
        run_polling()
