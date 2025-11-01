# app/core/supabase_client.py
from supabase import create_client, Client
from .config import settings

_supabase: Client | None = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        # ВАЖЛИВО: каст до str
        _supabase = create_client(str(settings.SUPABASE_URL), str(settings.SUPABASE_SERVICE_ROLE_KEY))
    return _supabase
