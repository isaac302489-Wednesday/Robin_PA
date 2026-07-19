"""Proactive scheduler - the bot messages YOU without being asked"""
from datetime import time, timedelta
from telegram.ext import Application

async def setup_user_schedules(application: Application, chat_id: int, user: dict):
    """Schedule daily briefings and reminders for a user"""
    job_queue = application.job_queue
    
    # Remove existing jobs for this user to avoid duplicates
    for job in job_queue.jobs():
        if job.name and str(chat_id) in job.name:
            job.schedule_removal()
    
    # Morning briefing (default 8:00 AM)
    job_queue.run_daily(
        morning_briefing_callback,
        time=time(hour=user.get('morning_hour', 8), minute=user.get('morning_minute', 0)),
        days=(0, 1, 2, 3, 4, 5, 6),
        data={"chat_id": chat_id},
        name=f"morning_{chat_id}"
    )
    
    # Evening briefing (default 8:00 PM)
    job_queue.run_daily(
        evening_briefing_callback,
        time=time(hour=user.get('evening_hour', 20), minute=user.get('evening_minute', 0)),
        days=(0, 1, 2, 3, 4, 5, 6),
        data={"chat_id": chat_id},
        name=f"evening_{chat_id}"
    )
    
    # Task reminders - check every 30 minutes
    job_queue.run_repeating(
        task_reminder_callback,
        interval=timedelta(minutes=30),
        first=timedelta(minutes=2),
        data={"chat_id": chat_id},
        name=f"reminders_{chat_id}"
    )

async def queue_research(application: Application, chat_id: int, query: str):
    """Queue background research - bot will message user when done"""
    job_queue = application.job_queue
    job_queue.run_once(
        research_callback,
        when=timedelta(seconds=3),
        data={"chat_id": chat_id, "query": query},
        name=f"research_{chat_id}_{hash(query) & 0xFFFFFFFF}"
    )

# ============ CALLBACKS ============

async def morning_briefing_callback(context):
    """Sends morning briefing proactively"""
    chat_id = context.job.data["chat_id"]
    
    from database import get_user_by_chat_id, get_today_tasks
    from ai_engine import generate_morning_briefing
    
    user = await get_user_by_chat_id(chat_id)
    if not user:
        return
    
    tasks = await get_today_tasks(user['id'])
    briefing = await generate_morning_briefing(user, tasks)
    
    try:
        await context.bot.send_message(chat_id, briefing, parse_mode="Markdown")
    except Exception as e:
        print(f"Morning briefing failed: {e}")

async def evening_briefing_callback(context):
    """Sends evening wrap-up proactively"""
    chat_id = context.job.data["chat_id"]
    
    from database import get_user_by_chat_id, get_pending_tasks
    from ai_engine import generate_evening_briefing
    
    user = await get_user_by_chat_id(chat_id)
    if not user:
        return
    
    tasks = await get_pending_tasks(user['id'])
    briefing = await generate_evening_briefing(user, tasks)
    
    try:
        await context.bot.send_message(chat_id, briefing, parse_mode="Markdown")
    except Exception as e:
        print(f"Evening briefing failed: {e}")

async def task_reminder_callback(context):
    """Checks for upcoming tasks and reminds user"""
    chat_id = context.job.data["chat_id"]
    
    from database import get_user_by_chat_id, get_upcoming_tasks
    
    user = await get_user_by_chat_id(chat_id)
    if not user:
        return
    
    upcoming = await get_upcoming_tasks(user['id'], minutes=35)
    
    for task in upcoming:
        try:
            time_str = task.get('due_time', 'soon')
            await context.bot.send_message(
                chat_id,
                f"⏰ *Reminder* \n\n📌 {task['title']}\n🕐 Due at {time_str}",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Reminder failed: {e}")

async def research_callback(context):
    """Background research - messages user when complete"""
    chat_id = context.job.data["chat_id"]
    query = context.job.data["query"]
    
    from database import get_user_by_chat_id, save_research_job, complete_research_job
    from research import search_web
    from ai_engine import summarize_research
    
    user = await get_user_by_chat_id(chat_id)
    if not user:
        return
    
    job_id = await save_research_job(user['id'], query)
    
    try:
        # Notify that research started
        await context.bot.send_message(
            chat_id,
            f"🔍 *Research started:* {query}\n\nI'll message you when it's ready...",
            parse_mode="Markdown"
        )
        
        # Do the research
        results = await search_web(query, max_results=8)
        
        if not results:
            await context.bot.send_message(
                chat_id,
                f"⚠️ *Research Issue*\n\nI couldn't find any web results for '{query}'.\n\n"
                f"This might be because:\n"
                f"• The search service is temporarily busy\n"
                f"• The query is too specific\n\n"
                f"Try rephrasing your request or try again in a few minutes.",
                parse_mode="Markdown"
            )
            await complete_research_job(job_id, "No results found")
            return
        
        summary = await summarize_research(query, results)
        
        # Save and send results
        await complete_research_job(job_id, summary)
        
        # Escape any problematic markdown characters
        safe_summary = summary.replace("*", "\\*").replace("_", "\\_").replace("[", "\\[").replace("]", "\\]")[:3800]
        
        await context.bot.send_message(
            chat_id,
            f"📊 *Research Complete*\n\n{safe_summary}",
            parse_mode="Markdown"
        )
        
    except Exception as e:
        error_msg = str(e)[:200]
        await context.bot.send_message(
            chat_id,
            f"❌ Research failed for '{query}'.\n\nError: {error_msg}\n\n"
            f"Please try again or rephrase your query."
        )