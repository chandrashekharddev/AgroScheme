# app/main.py - COMPLETE FIXED VERSION
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

# ✅ CORS Middleware - CRITICAL FIX
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# ✅ Global CORS middleware for all responses
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    origin = request.headers.get("origin")
    
    if origin:
        if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
    
    return response

# ✅ Handle OPTIONS preflight requests
@app.options("/{full_path:path}")
async def options_handler(request: Request, full_path: str):
    origin = request.headers.get("origin", "")
    response = JSONResponse(content={"message": "OK"}, status_code=200)
    
    if "vercel.app" in origin or origin in settings.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
        response.headers["Access-Control-Max-Age"] = "600"
    
    return response

# Create uploads directory
uploads_dir = Path(settings.UPLOAD_DIR)
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    print("=" * 50)
    print(f"🚀 Starting {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
    print(f"🔗 Supabase URL: {settings.SUPABASE_URL if hasattr(settings, 'SUPABASE_URL') else 'Not configured'}")
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
    
    # ✅ CRITICAL FIX: Import and include routers WITHOUT duplicate prefixes
    from app.routers import auth, farmers, schemes, documents, admin, upload
    
    app.include_router(auth.router)      # Auth already has /auth prefix
    app.include_router(farmers.router)   # Farmers already has /farmers prefix
    app.include_router(schemes.router)   # Schemes already has /schemes prefix
    app.include_router(documents.router) # Documents already has /documents prefix
    app.include_router(admin.router)     # Admin already has /admin prefix
    app.include_router(upload.router)
    
    print("✅ All routers loaded successfully")
    
    # Print all routes for debugging
    print("\n📋 Registered Routes:")
    routes_list = []
    for route in app.routes:
        if hasattr(route, 'methods') and route.path not in routes_list:
            routes_list.append(route.path)
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
        "your_origin": origin,
        "cors_allowed_origins": settings.ALLOWED_ORIGINS,
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

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to see all registered routes"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name
            })
    return {"routes": routes, "count": len(routes)}
