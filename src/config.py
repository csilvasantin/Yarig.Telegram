import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Yarig.ai
YARIG_EMAIL = os.getenv("YARIG_EMAIL", "")
YARIG_PASSWORD = os.getenv("YARIG_PASSWORD", "")

# Consejo de Administracion — LLM (desactivado por defecto, usa templates)
CONSEJO_USE_LLM = os.getenv("CONSEJO_USE_LLM", "false").lower() == "true"
CONSEJO_LLM_API_URL = os.getenv("CONSEJO_LLM_API_URL", "https://api.anthropic.com/v1/messages")
CONSEJO_LLM_API_KEY = os.getenv("CONSEJO_LLM_API_KEY", "")
CONSEJO_LLM_MODEL = os.getenv("CONSEJO_LLM_MODEL", "claude-sonnet-4-20250514")
CONSEJO_MAX_RESPONSE_LENGTH = int(os.getenv("CONSEJO_MAX_RESPONSE_LENGTH", "500"))
