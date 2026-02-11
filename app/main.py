# app/main.py - CRITICAL CORS FIX
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

# ✅ CRITICAL: CORS Middleware with EXPLICIT settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Must be exact strings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ✅ ADD THIS: Middleware to add CORS headers to EVERY response
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    
    # Allow your Vercel domain
    if origin and "vercel.app" in origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    # Also check allowed origins list
    elif origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# ✅ FIXED: Handle OPTIONS requests properly
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    origin = request.headers.get("origin", "")
    
    response = JSONResponse(
        content={"message": "OK"},
        status_code=200
    )
    
    # Allow your Vercel domain
    if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
        response.headers["Access-Control-Max-Age"] = "600"
    
    return response

# Create uploads directory
uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.on_event("startup")
async def startup_event():
    print("=" * 50)
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    print(f"🔗 Supabase URL: {settings.SUPABASE_URL}")
    print(f"🌐 CORS Allowed Origins: {settings.ALLOWED_ORIGINS}")
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
    
    # Import and include routers
    from app.routers import auth, farmers, schemes, documents, admin
    
    app.include_router(auth.router)  # NO PREFIX HERE
    app.include_router(farmers.router, prefix="/farmers")
    app.include_router(schemes.router, prefix="/schemes")
    app.include_router(documents.router, prefix="/documents")
    app.include_router(admin.router, prefix="/admin")

    print("✅ All routers loaded successfully")
    print("\n📋 Registered Routes:")
    for route in app.routes:
        if hasattr(route, 'methods'):
            print(f"  {list(route.methods)} - {route.path}")
    print("=" * 50)

@app.get("/")
async def root(request: Request):
    origin = request.headers.get("origin", "Not provided")
    return {
        "message": "AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "status": "running",
        "docs": "/docs",
        "supabase_configured": bool(settings.SUPABASE_URL and settings.SUPABASE_KEY),
        "your_origin": origin,
        "cors_allowed_origins": settings.ALLOWED_ORIGINS,
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
        "is_allowed": origin in settings.ALLOWED_ORIGINS or "vercel.app" in origin,
        "supabase_url": settings.SUPABASE_URL,
        "timestamp": datetime.utcnow().isoformat()
    }
