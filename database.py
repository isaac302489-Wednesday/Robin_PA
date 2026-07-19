"""SQLite database - all your data stored locally, completely free"""
import aiosqlite
from config import settings

async def init_db():
    """Create all tables on first run"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        # Users table - stores your chat ID so bot can message you anytime
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                timezone TEXT DEFAULT 'UTC',
                morning_hour INTEGER DEFAULT 8,
                morning_minute INTEGER DEFAULT 0,
                evening_hour INTEGER DEFAULT 20,
                evening_minute INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tasks table - everything the assistant organizes for you
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                due_time TEXT,
                priority INTEGER DEFAULT 2,
                status TEXT DEFAULT 'pending',
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Research jobs table - tracks background research
        await db.execute("""
            CREATE TABLE IF NOT EXISTS research_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                status TEXT DEFAULT 'queued',
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        await db.commit()

# ============ USER FUNCTIONS ============

async def get_or_create_user(chat_id: int, username: str = None):
    """Get existing user or create new one. Returns user as dict."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        row = await cursor.fetchone()

        if not row:
            await db.execute(
                "INSERT INTO users (chat_id, username) VALUES (?, ?)",
                (chat_id, username)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
            row = await cursor.fetchone()

        return dict(row)

async def get_user_by_chat_id(chat_id: int):
    """Get user by Telegram chat ID"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def update_user_settings(chat_id: int, morning_h: int, morning_m: int, evening_h: int, evening_m: int):
    """Update briefing times"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            UPDATE users 
            SET morning_hour=?, morning_minute=?, evening_hour=?, evening_minute=?
            WHERE chat_id=?
        """, (morning_h, morning_m, evening_h, evening_m, chat_id))
        await db.commit()

# ============ TASK FUNCTIONS ============

async def add_task(user_id: int, task: dict):
    """Save a task extracted from your messages"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            INSERT INTO tasks (user_id, title, due_date, due_time, priority, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            task.get("title", "Untitled"),
            task.get("due_date"),
            task.get("due_time"),
            task.get("priority", 2),
            task.get("source", "message")
        ))
        await db.commit()

async def get_today_tasks(user_id: int):
    """Get tasks due today"""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM tasks 
            WHERE user_id = ? AND due_date = ? AND status = 'pending'
            ORDER BY priority ASC, due_time ASC
        """, (user_id, today))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_pending_tasks(user_id: int):
    """Get all pending tasks"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM tasks 
            WHERE user_id = ? AND status = 'pending'
            ORDER BY due_date ASC, priority ASC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def get_upcoming_tasks(user_id: int, minutes: int = 35):
    """Get tasks due within the next X minutes"""
    from datetime import datetime, timedelta
    now = datetime.now()
    soon = (now + timedelta(minutes=minutes)).strftime("%H:%M")
    now_str = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM tasks 
            WHERE user_id = ? AND due_date = ? AND status = 'pending'
            AND due_time BETWEEN ? AND ?
            ORDER BY due_time ASC
        """, (user_id, today, now_str, soon))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def mark_task_done(task_id: int):
    """Mark a task as completed"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))
        await db.commit()

async def delete_task(task_id: int):
    """Delete a task"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()

# ============ RESEARCH FUNCTIONS ============

async def save_research_job(user_id: int, query: str):
    """Log a research request"""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO research_jobs (user_id, query) VALUES (?, ?)",
            (user_id, query)
        )
        await db.commit()
        return cursor.lastrowid

async def complete_research_job(job_id: int, result: str):
    """Mark research as complete with results"""
    from datetime import datetime
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            UPDATE research_jobs SET status = 'completed', result = ?, completed_at = ?
            WHERE id = ?
        """, (result, datetime.now().isoformat(), job_id))
        await db.commit()
