import os
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.config import settings
from app.database import get_db, Base, engine

# Create app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AgroScheme AI - AI-powered platform for farmers",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware - SIMPLE
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print("=" * 50)
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    print("=" * 50)
    
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        print("✅ Database connected and tables created")
        
    except Exception as e:
        print(f"⚠️ Database initialization failed: {str(e)}")
        print("⚠️ Some database features may not work")
    
    # Import and include routers
    from app.routers import auth, farmers, schemes, documents, admin
    
    app.include_router(auth.router, tags=["Authentication"])
    app.include_router(farmers.router, tags=["Farmers"])
    app.include_router(schemes.router, tags=["Schemes"])
    app.include_router(documents.router, tags=["Documents"])
    app.include_router(admin.router, tags=["Admin"])
    
    print("✅ All routers loaded successfully")
    print("✅ API ready to accept requests")

@app.get("/")
async def root():
    return {
        "message": "AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check with database connection test"""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "service": "agroscheme-api",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": "disconnected",
            "service": "agroscheme-api",
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/cors-test")
async def cors_test(request: Request):
    """Test CORS configuration"""
    origin = request.headers.get("origin", "Not provided")
    
    return {
        "message": "CORS test endpoint",
        "origin_received": origin,
        "allowed_origins": settings.ALLOWED_ORIGINS,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.options("/{full_path:path}")
async def preflight_handler():
    """Handle OPTIONS requests for all endpoints"""
    return JSONResponse(
        content={"message": "Preflight request successful"},
        headers={
            "Access-Control-Allow-Origin": ", ".join(settings.ALLOWED_ORIGINS),
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )
