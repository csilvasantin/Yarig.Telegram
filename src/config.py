import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_DAILY_CHAT_ID = os.getenv("TELEGRAM_DAILY_CHAT_ID", "")

# Yarig.ai
YARIG_EMAIL = os.getenv("YARIG_EMAIL", "")
YARIG_PASSWORD = os.getenv("YARIG_PASSWORD", "")

# Consejo AdmiraNext Game
CONSEJO_GAME_API_URL = os.getenv("CONSEJO_GAME_API_URL", "http://127.0.0.1:3030")

# Consejo de Administracion — LLM (desactivado por defecto, usa templates)
CONSEJO_USE_LLM = os.getenv("CONSEJO_USE_LLM", "false").lower() == "true"
CONSEJO_LLM_API_URL = os.getenv("CONSEJO_LLM_API_URL", "https://api.anthropic.com/v1/messages")
CONSEJO_LLM_API_KEY = os.getenv("CONSEJO_LLM_API_KEY", "")
CONSEJO_LLM_MODEL = os.getenv("CONSEJO_LLM_MODEL", "claude-sonnet-4-20250514")
CONSEJO_MAX_RESPONSE_LENGTH = int(os.getenv("CONSEJO_MAX_RESPONSE_LENGTH", "500"))

# Bots individuales de consejeros (crear via @BotFather)
BOT_TOKEN_CEO = os.getenv("BOT_TOKEN_CEO", "")
BOT_TOKEN_CFO = os.getenv("BOT_TOKEN_CFO", "")
BOT_TOKEN_COO = os.getenv("BOT_TOKEN_COO", "")
BOT_TOKEN_CTO = os.getenv("BOT_TOKEN_CTO", "")
BOT_TOKEN_CCO = os.getenv("BOT_TOKEN_CCO", "")
BOT_TOKEN_CSO = os.getenv("BOT_TOKEN_CSO", "")
BOT_TOKEN_CXO = os.getenv("BOT_TOKEN_CXO", "")
BOT_TOKEN_CDO = os.getenv("BOT_TOKEN_CDO", "")
