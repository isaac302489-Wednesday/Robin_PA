"""All Telegram message handlers - text, photo, voice, video, documents"""
import os
import re
import tempfile
from telegram import Update
from telegram.ext import ContextTypes

from database import (
    get_or_create_user, get_user_by_chat_id, add_task, get_today_tasks,
    get_pending_tasks, mark_task_done, delete_task, update_user_settings
)
from ai_engine import (
    extract_tasks_from_text, transcribe_voice, describe_image,
    process_general_message, classify_intent
)
from scheduler import setup_user_schedules, queue_research

# ============ COMMANDS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """First time setup - captures your chat ID for proactive messages"""
    chat_id = update.effective_chat.id
    username = update.effective_user.username
    
    user = await get_or_create_user(chat_id, username)
    await setup_user_schedules(context.application, chat_id, user)
    
    welcome = (
        "👋 *Hello! I'm your Personal Assistant.*\n\n"
        "✅ *What I do automatically:*\n"
        "• Morning briefing at 8:00 AM\n"
        "• Evening wrap-up at 8:00 PM\n"
        "• Remind you 30 min before tasks\n"
        "• Research anything in background\n\n"
        "✅ *What you can send me:*\n"
        "• 📝 Text messages (tasks, questions)\n"
        "• 🎙️ Voice messages (I transcribe them)\n"
        "• 📸 Photos (I read text & understand images)\n"
        "• 📄 Documents (PDF, Word, Excel, TXT)\n"
        "• 🎬 Videos (acknowledged, ask me to analyze)\n\n"
        "*Just talk to me naturally!* Try:\n"
        "`Remind me to call mom tomorrow at 5pm`\n"
        "`Research best wireless earbuds under $50`\n"
        "`What tasks do I have today?`"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available commands"""
    help_text = (
        "📋 *Commands:*\n\n"
        "/start - Setup or reset your assistant\n"
        "/tasks - Show today's tasks\n"
        "/alltasks - Show all pending tasks\n"
        "/done <number> - Mark a task done (e.g., /done 3)\n"
        "/delete <number> - Delete a task\n"
        "/settings - Change briefing times\n"
        "/research <topic> - Research something now\n"
        "/help - Show this message\n\n"
        "*Natural language examples:*\n"
        "• `Meeting with Sarah on Tuesday 2pm`\n"
        "• `Buy milk and eggs by Saturday`\n"
        "• `Research cheapest flights to Tokyo`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's tasks"""
    chat_id = update.effective_chat.id
    user = await get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return
    
    tasks = await get_today_tasks(user['id'])
    if not tasks:
        await update.message.reply_text("📭 *No tasks for today!* Enjoy your free time. 🎉", parse_mode="Markdown")
        return
    
    lines = ["📋 *Today's Tasks:*\n"]
    for i, t in enumerate(tasks, 1):
        prio = "🔴" if t['priority'] == 1 else "🟡" if t['priority'] == 2 else "🟢"
        time_str = f" _({t.get('due_time')})_" if t.get('due_time') else ""
        lines.append(f"{prio} {i}. {t['title']}{time_str}")
    
    lines.append("\n✏️ Reply with `/done <number>` to complete")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def alltasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all pending tasks"""
    chat_id = update.effective_chat.id
    user = await get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return
    
    tasks = await get_pending_tasks(user['id'])
    if not tasks:
        await update.message.reply_text("📭 *No pending tasks!*", parse_mode="Markdown")
        return
    
    lines = ["📋 *All Pending Tasks:*\n"]
    for i, t in enumerate(tasks, 1):
        date_str = f" 📅 {t['due_date']}" if t.get('due_date') else ""
        time_str = f" 🕐 {t['due_time']}" if t.get('due_time') else ""
        lines.append(f"{i}. {t['title']}{date_str}{time_str}")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark task as done by number"""
    chat_id = update.effective_chat.id
    user = await get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/done <task_number>`\nUse `/tasks` to see numbers.", parse_mode="Markdown")
        return
    
    try:
        num = int(context.args[0])
        tasks = await get_pending_tasks(user['id'])
        if num < 1 or num > len(tasks):
            await update.message.reply_text(f"Invalid number. You have {len(tasks)} pending tasks.")
            return
        
        task = tasks[num - 1]
        await mark_task_done(task['id'])
        await update.message.reply_text(f"✅ *Done!* {task['title']} completed. Great job! 🎉", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a task by number"""
    chat_id = update.effective_chat.id
    user = await get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: `/delete <task_number>`")
        return
    
    try:
        num = int(context.args[0])
        tasks = await get_pending_tasks(user['id'])
        if num < 1 or num > len(tasks):
            await update.message.reply_text(f"Invalid number. You have {len(tasks)} pending tasks.")
            return
        
        task = tasks[num - 1]
        await delete_task(task['id'])
        await update.message.reply_text(f"🗑️ Deleted: {task['title']}")
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change briefing times"""
    chat_id = update.effective_chat.id
    user = await get_user_by_chat_id(chat_id)
    if not user:
        await update.message.reply_text("Please run /start first!")
        return
    
    if len(context.args) < 4:
        current = (
            f"*Current Settings:*\n"
            f"Morning briefing: {user['morning_hour']:02d}:{user['morning_minute']:02d}\n"
            f"Evening briefing: {user['evening_hour']:02d}:{user['evening_minute']:02d}\n\n"
            f"To change: `/settings HH MM HH MM`\n"
            f"Example: `/settings 7 30 21 0` (7:30 AM, 9:00 PM)"
        )
        await update.message.reply_text(current, parse_mode="Markdown")
        return
    
    try:
        mh, mm, eh, em = int(context.args[0]), int(context.args[1]), int(context.args[2]), int(context.args[3])
        await update_user_settings(chat_id, mh, mm, eh, em)
        
        # Reschedule
        user = await get_user_by_chat_id(chat_id)
        await setup_user_schedules(context.application, chat_id, user)
        
        await update.message.reply_text(
            f"✅ Updated!\nMorning: {mh:02d}:{mm:02d}\nEvening: {eh:02d}:{em:02d}"
        )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Immediate research command"""
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Usage: `/research <topic>`\nExample: `/research best hiking trails near me`", parse_mode="Markdown")
        return
    
    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Starting research: *{query}*", parse_mode="Markdown")
    await queue_research(context.application, chat_id, query)

# ============ MESSAGE HANDLERS ============

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process all text messages - tasks, questions, research requests"""
    chat_id = update.effective_chat.id
    text = update.message.text
    user = await get_or_create_user(chat_id, update.effective_user.username)
    
    # 1. Check if it's a research request
    intent = await classify_intent(text)
    
    if intent == "research":
        await update.message.reply_text(
            f"🔍 Got it! Researching: *{text}*\n\nI'll message you when it's ready.",
            parse_mode="Markdown"
        )
        await queue_research(context.application, chat_id, text)
        return
    
    # 2. Try to extract tasks
    tasks = await extract_tasks_from_text(text)
    if tasks:
        for task in tasks:
            task['source'] = 'text_message'
            await add_task(user['id'], task)
        
        confirmations = "\n".join([f"✅ {t['title']}" for t in tasks])
        await update.message.reply_text(
            f"📌 *Saved {len(tasks)} task(s):*\n{confirmations}\n\nI'll remind you when it's time!",
            parse_mode="Markdown"
        )
        return
    
    # 3. Check for task-related keywords without AI extraction
    lower = text.lower()
    if any(k in lower for k in ["what tasks", "my tasks", "todo list", "what do i have"]):
        await tasks_cmd(update, context)
        return
    
    # 4. General conversation
    response = await process_general_message(text)
    await update.message.reply_text(response)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos - uses AI vision to understand images"""
    chat_id = update.effective_chat.id
    caption = update.message.caption or ""
    
    await update.message.reply_text("📸 Analyzing your photo...")
    
    # Download the largest photo
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await photo_file.download_to_drive(tmp.name)
        image_path = tmp.name
    
    try:
        # AI describes the image
        description = await describe_image(image_path, caption)
        
        # Try to extract tasks from description + caption
        combined = f"{caption}\nImage shows: {description}" if caption else description
        tasks = await extract_tasks_from_text(combined)
        
        user = await get_or_create_user(chat_id)
        if tasks:
            for task in tasks:
                task['source'] = 'photo'
                await add_task(user['id'], task)
            
            await update.message.reply_text(
                f"📝 *I found tasks in this image and saved them!*\n\n"
                f"📷 *Image analysis:*\n{description[:500]}...",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"📷 *Here's what I see:*\n{description}",
                parse_mode="Markdown"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not fully analyze photo: {str(e)[:200]}")
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - transcribe then process as text"""
    chat_id = update.effective_chat.id
    
    status_msg = await update.message.reply_text("🎙️ Transcribing your voice message...")
    
    # Download voice file (OGG format from Telegram)
    voice = update.message.voice
    voice_file = await voice.get_file()
    
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await voice_file.download_to_drive(tmp.name)
        voice_path = tmp.name
    
    try:
        # Transcribe with free Whisper API
        transcript = await transcribe_voice(voice_path)
        
        await status_msg.edit_text(f"📝 *You said:*\n_{transcript}_", parse_mode="Markdown")
        
        # Process transcribed text same as regular message
        user = await get_or_create_user(chat_id)
        tasks = await extract_tasks_from_text(transcript)
        
        if tasks:
            for task in tasks:
                task['source'] = 'voice'
                await add_task(user['id'], task)
            
            confirmations = "\n".join([f"✅ {t['title']}" for t in tasks])
            await update.message.reply_text(
                f"📌 *Saved from voice:*\n{confirmations}",
                parse_mode="Markdown"
            )
        else:
            # Treat as general message
            response = await process_general_message(transcript, context="voice message")
            await update.message.reply_text(response)
            
    except Exception as e:
        await update.message.reply_text(f"⚠️ Could not process voice: {str(e)[:200]}")
    finally:
        if os.path.exists(voice_path):
            os.unlink(voice_path)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle video messages"""
    await update.message.reply_text(
        "🎬 *Video received!*\n\n"
        "I can see you sent a video. Currently I can:\n"
        "• Save it as a note (tell me what it's about)\n"
        "• Research topics you mention in the caption\n\n"
        "*What would you like me to do with this video?*",
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle documents - PDF, Word, Excel, TXT"""
    chat_id = update.effective_chat.id
    doc = update.message.document
    file_name = doc.file_name or "document"
    
    await update.message.reply_text(f"📄 Processing *{file_name}*...", parse_mode="Markdown")
    
    # Download document
    doc_file = await doc.get_file()
    with tempfile.NamedTemporaryFile(suffix=f"_{file_name}", delete=False) as tmp:
        await doc_file.download_to_drive(tmp.name)
        doc_path = tmp.name
    
    try:
        text = extract_text_from_document(doc_path, file_name)
        
        if text:
            preview = text[:800] + "..." if len(text) > 800 else text
            
            await update.message.reply_text(
                f"📝 *Extracted from {file_name}:*\n```{preview[:400]}```\n...",
                parse_mode="Markdown"
            )
            
            # Extract tasks from document text
            user = await get_or_create_user(chat_id)
            tasks = await extract_tasks_from_text(text)
            
            if tasks:
                for task in tasks:
                    task['source'] = f'document:{file_name}'
                    await add_task(user['id'], task)
                
                confirmations = "\n".join([f"✅ {t['title']}" for t in tasks])
                await update.message.reply_text(
                    f"📌 *Found tasks in document:*\n{confirmations}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("No tasks found in this document, but I've read it.")
        else:
            await update.message.reply_text(
                "❌ Could not extract text from this file type.\n"
                "I support: PDF, Word (.docx), Excel (.xlsx), and plain text (.txt)"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error processing document: {str(e)[:200]}")
    finally:
        if os.path.exists(doc_path):
            os.unlink(doc_path)

def extract_text_from_document(path: str, filename: str) -> str:
    """Extract text from various document types"""
    lower = filename.lower()
    
    if lower.endswith('.txt'):
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    elif lower.endswith('.pdf'):
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except Exception as e:
            return f"[PDF error: {e}]"
    
    elif lower.endswith('.docx'):
        try:
            import docx
            document = docx.Document(path)
            return "\n".join([para.text for para in document.paragraphs])
        except Exception as e:
            return f"[DOCX error: {e}]"
    
    elif lower.endswith(('.xlsx', '.xls')):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, data_only=True)
            text = ""
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    row_text = " ".join(str(cell) for cell in row if cell is not None)
                    if row_text.strip():
                        text += row_text + "\n"
            return text
        except Exception as e:
            return f"[Excel error: {e}]"
    
    return ""