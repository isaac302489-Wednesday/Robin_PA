"""Configuration - reads from .env file"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    DB_PATH = os.getenv("DB_PATH", "assistant.db")

    # Free AI models
    TEXT_MODEL = "llama-3.1-70b-versatile"      # Groq free tier
    FAST_MODEL = "llama-3.1-8b-instant"         # Groq free tier (faster)
    WHISPER_MODEL = "whisper-large-v3"          # Groq free tier
    VISION_MODEL = "gemini-1.5-flash"           # Google free tier

settings = Settings()
