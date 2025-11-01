from datetime import datetime

def to_iso(value) -> str:
    # Supabase повертає рядок ISO або datetime — уніфікуємо
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)