# מדריך מימוש תיוג קבצים ב"אוספים שלי"

## סקירה כללית

מדריך זה מפרט את השלבים להוספת מערכת תיוג לפרומפטים השמורים, תוך שמירה על תאימות מלאה עם המבנה הקיים.

---

## תגיות זמינות

| אימוג'י | משמעות | שימוש מומלץ |
|---------|--------|-------------|
| 🐢 | לא דחוף | פרומפטים שאפשר לטפל בהם מאוחר יותר |
| 🔥 | דחוף | דורש טיפול מיידי |
| 🔮 | קסום | פרומפטים יוצאי דופן / מעניינים במיוחד |
| ♥️ | מועדף | פרומפטים שאהבת במיוחד |
| 🔐 | סודי | מידע רגיש / פרטי |
| 💭 | רעיון | השראה / רעיון לעתיד |
| ⏸️ | מושהה | עבודה שהופסקה באמצע |
| 🎯 | מטרה | יעד להשגה |
| 🐛 | באג | תיקון באג |
| 🗄️ | דאטה-בייס | קשור לבסיסי נתונים |
| 🧪 | ניסיוני | בדיקות / ניסויים |
| 1️⃣2️⃣3️⃣ | סדר טיפול | תעדוף בתוך אוסף |

---

## שלב 1: עדכון מודלים

### 1.1 הוספת Enum לתגיות

**קובץ:** `core/models.py`

```python
from enum import Enum

class PromptTag(str, Enum):
    """תגיות לסימון פרומפטים"""
    NOT_URGENT = "🐢"      # לא דחוף
    URGENT = "🔥"          # דחוף
    MAGIC = "🔮"           # קסום
    FAVORITE = "♥️"        # מועדף
    SECRET = "🔐"          # סודי
    IDEA = "💭"            # רעיון
    PAUSED = "⏸️"          # מושהה
    GOAL = "🎯"            # מטרה
    BUG = "🐛"             # באג
    DATABASE = "🗄️"        # דאטה-בייס
    TESTING = "🧪"         # ניסיוני
    PRIORITY_1 = "1️⃣"     # עדיפות 1
    PRIORITY_2 = "2️⃣"     # עדיפות 2
    PRIORITY_3 = "3️⃣"     # עדיפות 3
```

### 1.2 עדכון מודל PromptHistory

**קובץ:** `core/models.py`

הוסף שדות חדשים למחלקה `PromptHistory`:

```python
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class PromptHistory(BaseModel):
    """היסטוריית פרומפט עם תמיכה בתיוג"""
    user_id: str
    original_prompt: str
    improved_prompt: str
    category: PromptCategory
    weaknesses: List[Dict[str, Any]] = []
    score_before: int = 0
    score_after: int = 0
    iterations: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    feedback: Optional[str] = None
    rating: Optional[int] = None

    # === שדות חדשים לתיוג ===
    tags: List[str] = Field(default_factory=list)  # רשימת תגיות
    collection_name: Optional[str] = None          # שם האוסף
    priority_order: Optional[int] = None           # סדר בתוך אוסף
    is_archived: bool = False                      # האם בארכיון
    notes: Optional[str] = None                    # הערות חופשיות
```

---

## שלב 2: עדכון בסיס הנתונים

### 2.1 הוספת אינדקסים חדשים

**קובץ:** `database/mongodb.py`

הוסף לפונקציה `ensure_indexes()`:

```python
async def ensure_indexes(self):
    """יצירת אינדקסים כולל לתיוג"""
    prompt_history = self.db.prompt_history

    # אינדקסים קיימים
    await prompt_history.create_index("user_id")
    await prompt_history.create_index("category")
    await prompt_history.create_index([("created_at", -1)])
    await prompt_history.create_index([("category", 1), ("score_after", -1)])

    # === אינדקסים חדשים לתיוג ===
    await prompt_history.create_index("tags")  # חיפוש לפי תגית
    await prompt_history.create_index("collection_name")  # חיפוש לפי אוסף
    await prompt_history.create_index([
        ("user_id", 1),
        ("collection_name", 1),
        ("priority_order", 1)
    ])  # סדר בתוך אוסף
    await prompt_history.create_index([
        ("user_id", 1),
        ("is_archived", 1)
    ])  # פילטור ארכיון

    logger.info("Database indexes ensured (including tags)")
```

### 2.2 פונקציות חדשות לניהול תגיות

**קובץ:** `database/mongodb.py`

```python
async def add_tag(self, prompt_id: str, user_id: str, tag: str) -> bool:
    """הוספת תגית לפרומפט"""
    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        {"$addToSet": {"tags": tag}}
    )
    return result.modified_count > 0

async def remove_tag(self, prompt_id: str, user_id: str, tag: str) -> bool:
    """הסרת תגית מפרומפט"""
    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        {"$pull": {"tags": tag}}
    )
    return result.modified_count > 0

async def set_tags(self, prompt_id: str, user_id: str, tags: List[str]) -> bool:
    """עדכון כל התגיות של פרומפט"""
    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        {"$set": {"tags": tags}}
    )
    return result.modified_count > 0

async def get_by_tag(self, user_id: str, tag: str, limit: int = 20) -> List[Dict]:
    """שליפת פרומפטים לפי תגית"""
    cursor = self.db.prompt_history.find(
        {"user_id": user_id, "tags": tag, "is_archived": {"$ne": True}}
    ).sort("created_at", -1).limit(limit)

    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

async def get_user_tags(self, user_id: str) -> List[Dict[str, Any]]:
    """שליפת כל התגיות של משתמש עם ספירה"""
    pipeline = [
        {"$match": {"user_id": user_id, "is_archived": {"$ne": True}}},
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]

    results = []
    async for doc in self.db.prompt_history.aggregate(pipeline):
        results.append({"tag": doc["_id"], "count": doc["count"]})
    return results
```

### 2.3 פונקציות לניהול אוספים

**קובץ:** `database/mongodb.py`

```python
async def set_collection(
    self,
    prompt_id: str,
    user_id: str,
    collection_name: Optional[str],
    priority_order: Optional[int] = None
) -> bool:
    """הוספת פרומפט לאוסף"""
    update = {"$set": {"collection_name": collection_name}}
    if priority_order is not None:
        update["$set"]["priority_order"] = priority_order

    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        update
    )
    return result.modified_count > 0

async def get_collection(
    self,
    user_id: str,
    collection_name: str
) -> List[Dict]:
    """שליפת כל הפרומפטים באוסף"""
    cursor = self.db.prompt_history.find(
        {
            "user_id": user_id,
            "collection_name": collection_name,
            "is_archived": {"$ne": True}
        }
    ).sort("priority_order", 1)  # ממוין לפי סדר עדיפות

    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        results.append(doc)
    return results

async def get_user_collections(self, user_id: str) -> List[Dict[str, Any]]:
    """שליפת כל האוספים של משתמש"""
    pipeline = [
        {"$match": {
            "user_id": user_id,
            "collection_name": {"$ne": None},
            "is_archived": {"$ne": True}
        }},
        {"$group": {
            "_id": "$collection_name",
            "count": {"$sum": 1},
            "latest": {"$max": "$created_at"}
        }},
        {"$sort": {"latest": -1}}
    ]

    results = []
    async for doc in self.db.prompt_history.aggregate(pipeline):
        results.append({
            "name": doc["_id"],
            "count": doc["count"],
            "latest": doc["latest"]
        })
    return results

async def archive_prompt(self, prompt_id: str, user_id: str) -> bool:
    """העברת פרומפט לארכיון"""
    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        {"$set": {"is_archived": True}}
    )
    return result.modified_count > 0

async def unarchive_prompt(self, prompt_id: str, user_id: str) -> bool:
    """שחזור פרומפט מארכיון"""
    result = await self.db.prompt_history.update_one(
        {"_id": ObjectId(prompt_id), "user_id": user_id},
        {"$set": {"is_archived": False}}
    )
    return result.modified_count > 0
```

---

## שלב 3: פקודות בוט חדשות

### 3.1 רשימת פקודות

| פקודה | תיאור |
|-------|-------|
| `/mytags` | הצגת כל התגיות שלי |
| `/tag` | תיוג הפרומפט האחרון |
| `/collections` | הצגת האוספים שלי |
| `/collection [שם]` | צפייה באוסף ספציפי |
| `/favorites` | קיצור ל-♥️ מועדפים |
| `/urgent` | קיצור ל-🔥 דחופים |

### 3.2 הוספת Handlers

**קובץ:** `bot.py`

```python
# === תגיות זמינות ===
AVAILABLE_TAGS = {
    "🐢": "לא דחוף",
    "🔥": "דחוף",
    "🔮": "קסום",
    "♥️": "מועדף",
    "🔐": "סודי",
    "💭": "רעיון",
    "⏸️": "מושהה",
    "🎯": "מטרה",
    "🐛": "באג",
    "🗄️": "דאטה-בייס",
    "🧪": "ניסיוני",
    "1️⃣": "עדיפות 1",
    "2️⃣": "עדיפות 2",
    "3️⃣": "עדיפות 3",
}


async def mytags_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /mytags - הצגת כל התגיות של המשתמש"""
    user_id = str(update.effective_user.id)
    db = MongoDB()

    tags = await db.get_user_tags(user_id)

    if not tags:
        await update.message.reply_text(
            "📭 אין לך עדיין פרומפטים מתויגים.\n\n"
            "השתמש ב-/tag אחרי שיפור פרומפט כדי לתייג אותו."
        )
        return

    text = "🏷️ **התגיות שלי:**\n\n"
    for item in tags:
        tag = item["tag"]
        count = item["count"]
        name = AVAILABLE_TAGS.get(tag, "")
        text += f"{tag} {name}: {count} פרומפטים\n"

    text += "\n💡 לחץ על תגית לצפייה בפרומפטים"

    # יצירת כפתורים לכל תגית
    keyboard = []
    row = []
    for item in tags:
        tag = item["tag"]
        row.append(InlineKeyboardButton(
            f"{tag} ({item['count']})",
            callback_data=f"viewtag:{tag}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /tag - תיוג הפרומפט האחרון"""
    user_id = str(update.effective_user.id)
    db = MongoDB()

    # שליפת הפרומפט האחרון
    history = await db.get_user_history(user_id, limit=1)
    if not history:
        await update.message.reply_text(
            "❌ אין לך פרומפטים שמורים עדיין."
        )
        return

    prompt_id = history[0]["_id"]
    current_tags = history[0].get("tags", [])

    # שמירה ב-context לשימוש ב-callback
    context.user_data["tagging_prompt_id"] = prompt_id

    text = "🏷️ **בחר תגיות לפרומפט:**\n\n"
    text += f"📝 {history[0]['original_prompt'][:50]}...\n\n"

    if current_tags:
        text += f"תגיות נוכחיות: {' '.join(current_tags)}\n"

    # יצירת כפתורי תגיות
    keyboard = []
    row = []
    for emoji, name in AVAILABLE_TAGS.items():
        # סימון אם התגית כבר קיימת
        prefix = "✓ " if emoji in current_tags else ""
        row.append(InlineKeyboardButton(
            f"{prefix}{emoji}",
            callback_data=f"toggle_tag:{emoji}"
        ))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # כפתור סיום
    keyboard.append([InlineKeyboardButton("✅ סיום", callback_data="tag_done")])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def collections_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /collections - הצגת האוספים"""
    user_id = str(update.effective_user.id)
    db = MongoDB()

    collections = await db.get_user_collections(user_id)

    if not collections:
        await update.message.reply_text(
            "📂 אין לך אוספים עדיין.\n\n"
            "כדי ליצור אוסף, תייג פרומפט והוסף אותו לאוסף."
        )
        return

    text = "📚 **האוספים שלי:**\n\n"
    for coll in collections:
        text += f"📁 **{coll['name']}** ({coll['count']} פרומפטים)\n"

    # כפתורים לכל אוסף
    keyboard = []
    for coll in collections:
        keyboard.append([InlineKeyboardButton(
            f"📁 {coll['name']} ({coll['count']})",
            callback_data=f"viewcoll:{coll['name']}"
        )])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת /favorites - קיצור למועדפים"""
    user_id = str(update.effective_user.id)
    db = MongoDB()

    prompts = await db.get_by_tag(user_id, "♥️", limit=10)

    if not prompts:
        await update.message.reply_text(
            "♥️ אין לך מועדפים עדיין.\n\n"
            "השתמש ב-/tag והוסף ♥️ לפרומפטים שאתה אוהב."
        )
        return

    text = "♥️ **המועדפים שלי:**\n\n"
    for i, p in enumerate(prompts, 1):
        tags = " ".join(p.get("tags", []))
        text += f"{i}. {p['original_prompt'][:40]}... {tags}\n"

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
```

### 3.3 עדכון Callback Handler

**קובץ:** `bot.py`

הוסף לפונקציה `handle_callback`:

```python
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול ב-callbacks כולל תיוג"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = str(update.effective_user.id)
    db = MongoDB()

    # === Callbacks קיימים ===
    if data.startswith("improve:"):
        # ... קוד קיים ...
        pass

    elif data.startswith("rate:"):
        # ... קוד קיים ...
        pass

    # === Callbacks חדשים לתיוג ===
    elif data.startswith("toggle_tag:"):
        tag = data.split(":")[1]
        prompt_id = context.user_data.get("tagging_prompt_id")

        if not prompt_id:
            await query.edit_message_text("❌ שגיאה: לא נמצא פרומפט")
            return

        # שליפת התגיות הנוכחיות
        history = await db.get_user_history(user_id, limit=1)
        current_tags = history[0].get("tags", []) if history else []

        # החלפת מצב התגית
        if tag in current_tags:
            current_tags.remove(tag)
            await db.remove_tag(prompt_id, user_id, tag)
        else:
            current_tags.append(tag)
            await db.add_tag(prompt_id, user_id, tag)

        # עדכון הכפתורים
        keyboard = []
        row = []
        for emoji, name in AVAILABLE_TAGS.items():
            prefix = "✓ " if emoji in current_tags else ""
            row.append(InlineKeyboardButton(
                f"{prefix}{emoji}",
                callback_data=f"toggle_tag:{emoji}"
            ))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("✅ סיום", callback_data="tag_done")])

        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "tag_done":
        prompt_id = context.user_data.get("tagging_prompt_id")
        history = await db.get_user_history(user_id, limit=1)
        tags = history[0].get("tags", []) if history else []

        if tags:
            await query.edit_message_text(
                f"✅ התגיות נשמרו: {' '.join(tags)}"
            )
        else:
            await query.edit_message_text("✅ התגיות הוסרו")

        context.user_data.pop("tagging_prompt_id", None)

    elif data.startswith("viewtag:"):
        tag = data.split(":")[1]
        prompts = await db.get_by_tag(user_id, tag, limit=10)

        tag_name = AVAILABLE_TAGS.get(tag, "")
        text = f"{tag} **{tag_name}:**\n\n"

        for i, p in enumerate(prompts, 1):
            text += f"{i}. {p['original_prompt'][:40]}...\n"

        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

    elif data.startswith("viewcoll:"):
        coll_name = data.split(":")[1]
        prompts = await db.get_collection(user_id, coll_name)

        text = f"📁 **{coll_name}:**\n\n"

        for i, p in enumerate(prompts, 1):
            tags = " ".join(p.get("tags", []))
            order = p.get("priority_order", "")
            order_str = f"[{order}] " if order else ""
            text += f"{order_str}{i}. {p['original_prompt'][:35]}... {tags}\n"

        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
```

### 3.4 רישום הפקודות החדשות

**קובץ:** `bot.py`

עדכן את פונקציית `create_bot()`:

```python
def create_bot() -> Application:
    """יצירת הבוט"""
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # פקודות קיימות
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("improve", improve_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("examples", examples_command))

    # === פקודות חדשות לתיוג ===
    application.add_handler(CommandHandler("mytags", mytags_command))
    application.add_handler(CommandHandler("tag", tag_command))
    application.add_handler(CommandHandler("collections", collections_command))
    application.add_handler(CommandHandler("favorites", favorites_command))
    application.add_handler(CommandHandler("urgent", urgent_command))  # דומה ל-favorites עם 🔥

    # הודעות טקסט
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    # Callbacks
    application.add_handler(CallbackQueryHandler(handle_callback))

    return application
```

---

## שלב 4: תוספת לממשק אחרי שיפור

### 4.1 הוספת כפתור תיוג אחרי שיפור

**קובץ:** `bot.py`

עדכן את פונקציית `improve_prompt()` להוסיף כפתור תיוג:

```python
async def improve_prompt(update_or_query, user_id: str, prompt: str):
    """שיפור פרומפט עם כפתור תיוג"""
    # ... קוד קיים לשיפור ...

    # הוספת כפתורים כולל תיוג
    keyboard = [
        [
            InlineKeyboardButton("⭐ 1", callback_data=f"rate:1:{user_id}"),
            InlineKeyboardButton("⭐ 2", callback_data=f"rate:2:{user_id}"),
            InlineKeyboardButton("⭐ 3", callback_data=f"rate:3:{user_id}"),
            InlineKeyboardButton("⭐ 4", callback_data=f"rate:4:{user_id}"),
            InlineKeyboardButton("⭐ 5", callback_data=f"rate:5:{user_id}"),
        ],
        [
            InlineKeyboardButton("🏷️ תייג", callback_data=f"tag_prompt:{prompt_id}"),
            InlineKeyboardButton("📁 הוסף לאוסף", callback_data=f"add_to_coll:{prompt_id}"),
        ]
    ]

    await message.reply_text(
        response_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
```

---

## שלב 5: מיגרציה לנתונים קיימים

### 5.1 סקריפט מיגרציה

צור קובץ `scripts/migrate_tags.py`:

```python
"""
סקריפט מיגרציה - הוספת שדות תיוג לפרומפטים קיימים
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import config

async def migrate():
    client = AsyncIOMotorClient(config.MONGODB_URI)
    db = client[config.MONGODB_DB_NAME]

    # הוספת שדות ברירת מחדל לכל המסמכים הקיימים
    result = await db.prompt_history.update_many(
        {"tags": {"$exists": False}},  # רק מסמכים ללא tags
        {"$set": {
            "tags": [],
            "collection_name": None,
            "priority_order": None,
            "is_archived": False,
            "notes": None
        }}
    )

    print(f"Updated {result.modified_count} documents")

    # יצירת אינדקסים חדשים
    await db.prompt_history.create_index("tags")
    await db.prompt_history.create_index("collection_name")
    await db.prompt_history.create_index([
        ("user_id", 1),
        ("collection_name", 1),
        ("priority_order", 1)
    ])

    print("Indexes created")

if __name__ == "__main__":
    asyncio.run(migrate())
```

---

## שלב 6: עדכון הודעת עזרה

### 6.1 עדכון help_command

**קובץ:** `bot.py`

הוסף לטקסט העזרה:

```python
help_text = """📖 **מדריך שימוש**

... (טקסט קיים) ...

**🏷️ תיוג ואוספים:**
/tag - תייג את הפרומפט האחרון
/mytags - צפה בכל התגיות שלך
/collections - צפה באוספים שלך
/favorites - צפה במועדפים (♥️)
/urgent - צפה בדחופים (🔥)

**תגיות זמינות:**
🐢 לא דחוף | 🔥 דחוף | 🔮 קסום
♥️ מועדף | 🔐 סודי | 💭 רעיון
⏸️ מושהה | 🎯 מטרה | 🐛 באג
🗄️ DB | 🧪 ניסיוני | 1️⃣2️⃣3️⃣ עדיפות
"""
```

---

## סיכום מבנה הקבצים

```
prompt-enhancer/
├── core/
│   └── models.py          # + PromptTag enum, שדות חדשים ב-PromptHistory
├── database/
│   └── mongodb.py         # + פונקציות תיוג ואוספים
├── bot.py                 # + handlers חדשים + callbacks
├── scripts/
│   └── migrate_tags.py    # סקריפט מיגרציה (חדש)
└── docs/
    └── TAGGING_IMPLEMENTATION_GUIDE.md  # מדריך זה
```

---

## בדיקות מומלצות

1. **תיוג בסיסי:** שפר פרומפט → /tag → בחר תגיות → בדוק שנשמרו
2. **צפייה בתגיות:** /mytags → לחץ על תגית → וודא תצוגה נכונה
3. **אוספים:** צור אוסף → הוסף פרומפטים → /collections → צפה באוסף
4. **מיגרציה:** הרץ סקריפט מיגרציה → וודא שפרומפטים ישנים קיבלו שדות
5. **עדיפות:** הוסף 1️⃣2️⃣3️⃣ לפרומפטים באוסף → וודא סדר נכון

---

## הערות נוספות

- כל השינויים תואמים ל-MongoDB schema הקיים
- אין שבירה של backwards compatibility
- פרומפטים ישנים ימשיכו לעבוד ללא תגיות
- התגיות מאוחסנות כ-strings פשוטים (אימוג'ים)
- ניתן להרחיב בקלות עם תגיות נוספות בעתיד
