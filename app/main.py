# app/main.py - SIMPLIFIED VERSION
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Direct imports
from database import engine, Base
from config import settings

# Import routers
try:
    from routers import auth, farmers, schemes, admin, documents
    ROUTERS_AVAILABLE = True
except ImportError:
    ROUTERS_AVAILABLE = False
    print("Note: Some routers not available yet")

# ✅ Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AgroScheme AI - AI-powered platform for farmers"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
uploads_dir = Path(settings.UPLOAD_DIR)
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# ✅ Include routers only if available
if ROUTERS_AVAILABLE:
    app.include_router(auth.router)
    app.include_router(farmers.router)
    app.include_router(schemes.router)
    app.include_router(admin.router)
    app.include_router(documents.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agroscheme-api",
        "database": "connected" if engine else "disconnected"
    }

# ✅ Simple test endpoints
@app.get("/test")
async def test_endpoint():
    return {"message": "API is working!"}

@app.post("/test-auth")
async def test_auth():
    return {"message": "Auth endpoint test"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )