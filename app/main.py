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

# Create app FIRST
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AgroScheme AI - AI-powered platform for farmers",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware - UPDATED WITH COMPLETE CONFIGURATION
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=settings.ALLOW_CREDENTIALS,
    allow_methods=settings.ALLOW_METHODS,
    allow_headers=settings.ALLOW_HEADERS,
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Create uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Store initialization state
app.state.database_initialized = False
app.state.database_engine = engine

# Custom middleware for CORS headers
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Add CORS headers to all responses
    origin = request.headers.get("origin")
    
    if origin and origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
    elif "*" in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = "*"
    
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = ", ".join(settings.ALLOW_METHODS)
    response.headers["Access-Control-Allow-Headers"] = ", ".join(settings.ALLOW_HEADERS)
    response.headers["Access-Control-Expose-Headers"] = "*"
    
    return response

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print("=" * 50)
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    print(f"📊 Database: {settings.database_type}")
    print(f"🌐 Allowed Origins: {len(settings.ALLOWED_ORIGINS)} origins configured")
    print("=" * 50)
    
    try:
        # Test database connection WITH text()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        app.state.database_initialized = True
        print("✅ Database connected and tables created")
        
    except Exception as e:
        print(f"⚠️ Database initialization failed: {str(e)}")
        print("⚠️ Some database features may not work")
        app.state.database_initialized = False
    
    # Now import and include routers
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
        "database": "connected" if app.state.database_initialized else "disconnected",
        "docs": "/docs",
        "health": "/health",
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
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/cors-test")
async def cors_test(request: Request):
    """Test CORS configuration"""
    origin = request.headers.get("origin", "Not provided")
    
    return {
        "message": "CORS test endpoint",
        "origin_received": origin,
        "origin_allowed": origin in settings.ALLOWED_ORIGINS,
        "allowed_origins_count": len(settings.ALLOWED_ORIGINS),
        "timestamp": datetime.utcnow().isoformat(),
        "headers_received": dict(request.headers)
    }

@app.get("/debug")
async def debug():
    """Debug endpoint"""
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION,
        "database_initialized": app.state.database_initialized,
        "database_type": settings.database_type,
        "cors_enabled": True,
        "allowed_origins": settings.ALLOWED_ORIGINS,
        "environment": "production",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.options("/{full_path:path}")
async def preflight_handler(full_path: str):
    """Handle OPTIONS requests for all endpoints"""
    return JSONResponse(
        content={"message": "Preflight request successful"},
        headers={
            "Access-Control-Allow-Origin": ", ".join(settings.ALLOWED_ORIGINS),
            "Access-Control-Allow-Methods": ", ".join(settings.ALLOW_METHODS),
            "Access-Control-Allow-Headers": ", ".join(settings.ALLOW_HEADERS),
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "600"
        }
    )

@app.get("/test")
async def test():
    return {"message": "API working", "timestamp": datetime.utcnow().isoformat()}
