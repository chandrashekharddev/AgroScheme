# app/main.py
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ✅ All imports should start with app.
from app.database import engine, Base
from app.config import settings
from app.routers import auth, farmers, schemes, documents, admin

# ✅ Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AgroScheme AI - AI-powered platform for farmers"
)

# CORS
allowed_origins = settings.ALLOWED_ORIGINS.copy()
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
if RENDER_URL:
    allowed_origins.append(RENDER_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory (for SQLite only)
if "sqlite" in settings.DATABASE_URL:
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
else:
    print("⚠️ PostgreSQL: uploads/ not mounted")

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
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agroscheme-api"}

@app.get("/test")
async def test():
    return {"message": "API working"}