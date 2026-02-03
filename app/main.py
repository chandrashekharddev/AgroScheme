# app/main.py - ADD DEBUG LOGGING
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Imports
from app.database import engine, Base
from app.config import settings
from app.routers import auth, farmers, schemes, documents, admin

os.makedirs("uploads", exist_ok=True)
# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AI-powered platform for farmers"
)

# ✅ PRINT CORS INFO FOR DEBUGGING
print("=" * 50)
print("CORS Configuration:")
print(f"Allowed Origins: {settings.ALLOWED_ORIGINS}")
print(f"Request Origin (from env): {os.getenv('REQUEST_ORIGIN', 'Not set')}")
print("=" * 50)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ FIXED: Create uploads directory properly
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers
app.include_router(auth.router, tags=["Authentication"])
app.include_router(farmers.router, tags=["Farmers"])
app.include_router(schemes.router, tags=["Schemes"])
app.include_router(documents.router, tags=["Documents"])
app.include_router(admin.router, tags=["Admin"])

@app.get("/")
async def root():
    return {
        "message": "AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs",
        "health": "/health",
        "cors_enabled": True,
        "allowed_origins": settings.ALLOWED_ORIGINS[:3]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agroscheme-api"}

@app.get("/test")
async def test():
    return {"message": "API working"}

@app.get("/cors-test")
async def cors_test():
    return {
        "message": "CORS test successful",
        "allowed_origins": settings.ALLOWED_ORIGINS,
        "timestamp": "now"
    }

@app.options("/{path:path}")
async def options_handler():
    return {"message": "CORS preflight OK"}
