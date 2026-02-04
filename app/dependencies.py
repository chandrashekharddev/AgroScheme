# app/dependencies.py
from fastapi import HTTPException, status

def verify_admin():
    """
    Admin verification for development
    Accepts all requests as admin
    """
    return {
        "id": 0,
        "username": "admin",
        "full_name": "System Administrator",
        "role": "admin",
        "is_admin": True
    }
