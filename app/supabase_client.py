# app/supabase_client.py
from supabase import create_client, Client
from app.config import settings
import os

# Initialize Supabase client with your exact env vars
_supabase_client = None
_supabase_admin = None

def get_supabase_client() -> Client:
    """Get Supabase client with anon key"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        print(f"✅ Supabase client initialized with URL: {settings.SUPABASE_URL}")
    return _supabase_client

def get_supabase_admin() -> Client:
    """Get Supabase admin client with service role key"""
    global _supabase_admin
    if _supabase_admin is None:
        # You need to add SUPABASE_SERVICE_KEY to your env variables
        service_key = os.getenv("SUPABASE_SERVICE_KEY", settings.SUPABASE_KEY)
        _supabase_admin = create_client(
            settings.SUPABASE_URL,
            service_key
        )
    return _supabase_admin
