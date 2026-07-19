"""AI brain - uses completely free APIs"""
import json
import asyncio
from groq import AsyncGroq
import google.generativeai as genai
from config import settings

# Initialize clients
groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
genai.configure(api_key=settings.GEMINI_API_KEY)

async def extract_tasks_from_text(text: str):
    """Use AI to find tasks in your messages"""
    prompt = f"""Analyze this message and extract any tasks, events, reminders, or deadlines.
Return ONLY a JSON array like this:
[{{"title": "Buy groceries", "due_date": "2026-07-20", "due_time": "18:00", "priority": 2}}]

Rules:
- due_date format: YYYY-MM-DD or null if not mentioned
- due_time format: HH:MM or null if not mentioned  
- priority: 1=urgent, 2=normal, 3=low
- If no tasks found, return: []

User message: {text}"""

    try:
        response = await groq_client.chat.completions.create(
            model=settings.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        content = response.choices[0].message.content
        # Clean markdown code blocks
        content = content.replace("```json", "").replace("```", "").strip()
        tasks = json.loads(content)
        return tasks if isinstance(tasks, list) else []
    except Exception as e:
        print(f"Task extraction error: {e}")
        return []

async def generate_morning_briefing(user: dict, tasks: list):
    """Create your morning briefing"""
    task_text = "\n".join([f"- {t['title']} (due: {t.get('due_time', 'anytime')})" for t in tasks]) if tasks else "No tasks scheduled for today."

    prompt = f"""You are a warm, proactive personal assistant. Create a morning briefing.

User timezone: {user.get('timezone', 'UTC')}
Tasks today: {task_text}

Format with emojis. Include:
1. Friendly greeting with the day of week
2. Overview of today's tasks
3. Highlight anything urgent (priority 1)
4. Brief motivational closing

Keep it under 300 words."""

    try:
        response = await groq_client.chat.completions.create(
            model=settings.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"☀️ Good morning!\n\n📋 Today's tasks:\n{task_text}\n\nHave a productive day! 💪"

async def generate_evening_briefing(user: dict, tasks: list):
    """Create your evening wrap-up"""
    task_text = "\n".join([f"- {t['title']}" for t in tasks]) if tasks else "No remaining tasks for today."

    prompt = f"""You are a personal assistant. Create an evening wrap-up.

Remaining tasks: {task_text}

Format with emojis. Include:
1. Friendly evening greeting
2. What is still pending (if anything)
3. Encouragement to rest
4. Brief preview of tomorrow if tasks exist

Keep it warm and under 200 words."""

    try:
        response = await groq_client.chat.completions.create(
            model=settings.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"🌙 Evening wrap-up\n\nPending tasks:\n{task_text}\n\nGreat work today! Rest well. 😊"

async def transcribe_voice(audio_path: str):
    """Convert voice messages to text using free Whisper API"""
    try:
        with open(audio_path, "rb") as audio_file:
            response = await groq_client.audio.transcriptions.create(
                model=settings.WHISPER_MODEL,
                file=audio_file,
                response_format="text"
            )
        return response
    except Exception as e:
        return f"[Could not transcribe: {str(e)}]"

async def describe_image(image_path: str, caption: str = ""):
    """Understand photos using free Gemini vision"""
    try:
        model = genai.GenerativeModel(settings.VISION_MODEL)
        image = genai.upload_file(image_path)

        prompt = "Describe this image in detail. If it contains text, transcribe it."
        if caption:
            prompt += f" The user also said: '{caption}'"

        # Run sync Gemini call in thread pool so it doesn't block
        response = await asyncio.to_thread(
            lambda: model.generate_content([prompt, image]).text
        )
        return response
    except Exception as e:
        return f"[Could not analyze image: {str(e)}]"

async def summarize_research(query: str, search_results: list):
    """Summarize web research findings"""
    results_text = "\n\n".join([
        f"Source: {r.get('title', 'Unknown')}\n{r.get('snippet', '')}\nURL: {r.get('url', '')}"
        for r in search_results
    ])

    prompt = f"""Research query: {query}

Search results:
{results_text}

Provide a comprehensive but concise summary. Structure:
1. 📌 Key Findings (bullet points)
2. 🔗 Sources mentioned
3. 💡 Actionable recommendations

Keep under 400 words."""

    try:
        response = await groq_client.chat.completions.create(
            model=settings.TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Research on '{query}':\n\n{results_text[:1000]}..."

async def process_general_message(text: str, context: str = ""):
    """Handle any general message naturally"""
    prompt = f"""You are a helpful personal assistant. The user said: "{text}"

Context: {context}

Respond helpfully and concisely. If they mentioned a task, confirm you saved it. 
If they asked a question, answer it. If they seem stressed, be supportive.
Keep under 150 words."""

    try:
        response = await groq_client.chat.completions.create(
            model=settings.FAST_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return "I received your message and I'm processing it. How else can I help?"

async def classify_intent(text: str):
    """Figure out what the user wants"""
    lower = text.lower()
    if any(k in lower for k in ["research", "find out", "look up", "search for", "investigate", "tell me about", "what is", "how to"]):
        return "research"
    if any(k in lower for k in ["task", "todo", "remind me", "due", "deadline", "schedule", "appointment", "meeting"]):
        return "task"
    return "chat"
