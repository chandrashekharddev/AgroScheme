# app/main.py - Updated CORS Middleware
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

# ✅ FIXED: CORS Middleware with explicit origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Allow-Origin",
        "Access-Control-Allow-Credentials",
        "Access-Control-Allow-Methods",
        "Access-Control-Allow-Headers"
    ],
    expose_headers=["Content-Type", "Authorization"],
    max_age=600  # Cache preflight requests for 10 minutes
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
    
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(farmers.router, prefix="/farmers", tags=["Farmers"])
    app.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])
    app.include_router(admin.router, prefix="/admin", tags=["Admin"])
    
    print("✅ All routers loaded successfully")
    print("✅ API ready to accept requests")
    print(f"✅ CORS Allowed Origins: {settings.ALLOWED_ORIGINS}")

@app.get("/")
async def root():
    return {
        "message": "AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "cors_enabled": True,
        "allowed_origins": settings.ALLOWED_ORIGINS,
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
        "is_allowed": origin in settings.ALLOWED_ORIGINS,
        "timestamp": datetime.utcnow().isoformat()
    }

# ✅ FIXED: Proper OPTIONS handler
@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    """Handle OPTIONS requests for all endpoints"""
    origin = request.headers.get("origin", "")
    
    response = JSONResponse(
        content={"message": "Preflight request successful"},
        status_code=200
    )
    
    # Dynamically set CORS headers
    if origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
    elif settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = settings.ALLOWED_ORIGINS[0]
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin, X-Requested-With"
    response.headers["Access-Control-Max-Age"] = "600"
    
    return response
