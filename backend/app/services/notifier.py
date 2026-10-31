import httpx
from app.config import settings

# Dispatches real-time emergency relief alerts to telegram channels if configured
def send_telegram_alert(message: str) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID

    # Fallback silently if Telegram bot credentials are not set in .env
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False
