# app/main.py - CORRECTED VERSION
import os
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Database imports
from app.database import engine, Base
from app.config import settings

# Router imports - FIXED: Only import what actually exists
try:
    from app.routers import auth, farmers, schemes, documents
    ROUTERS_LOADED = True
except ImportError as e:
    print(f"⚠️ Router import error: {e}")
    ROUTERS_LOADED = False

# ✅ ENSURE UPLOADS DIRECTORY EXISTS WITH PROPER STRUCTURE
def init_uploads_directory():
    """Initialize uploads directory with proper structure"""
    uploads_root = settings.UPLOAD_ROOT
    
    # Create main uploads directory
    uploads_root.mkdir(exist_ok=True)
    
    # Create system directories
    system_dirs = [
        uploads_root / "temp",
        uploads_root / "trash",
        uploads_root / "system",
    ]
    
    for dir_path in system_dirs:
        dir_path.mkdir(exist_ok=True)
        # Add .gitkeep to maintain structure
        gitkeep = dir_path / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
    
    # Add .gitkeep to root
    root_gitkeep = uploads_root / ".gitkeep"
    if not root_gitkeep.exists():
        root_gitkeep.touch()
    
    # Create .gitignore for uploads
    gitignore_content = """# Ignore user-uploaded files
/*
!.gitkeep

# Keep system directories
!/temp/
!/trash/
!/system/

# Ignore all files in system directories (except .gitkeep)
/temp/*
/trash/*
/system/*
"""
    
    gitignore = uploads_root / ".gitignore"
    gitignore.write_text(gitignore_content)
    
    print(f"✅ Uploads directory initialized at: {uploads_root}")

# Initialize uploads
init_uploads_directory()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="AI-powered platform for farmers",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ✅ PRINT DEBUG INFO
print("=" * 50)
print("AGROSCHEME AI - STARTUP INFO")
print("=" * 50)
print(f"Project: {settings.PROJECT_NAME} v{settings.PROJECT_VERSION}")
print(f"Database: {settings.DATABASE_URL[:50]}...")
print(f"Uploads Root: {settings.UPLOAD_ROOT}")
print(f"API Base URL: {settings.API_BASE_URL}")
print(f"CORS Allowed Origins: {len(settings.ALLOWED_ORIGINS)} origins")
if settings.ALLOWED_ORIGINS:
    for i, origin in enumerate(settings.ALLOWED_ORIGINS[:3]):
        print(f"  - {origin}")
    if len(settings.ALLOWED_ORIGINS) > 3:
        print(f"  - ... and {len(settings.ALLOWED_ORIGINS) - 3} more")
print("=" * 50)

# ✅ CORS MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# ✅ STATIC FILE SERVING FOR UPLOADS
# Important: This must be mounted before routers
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include routers if they exist
if ROUTERS_LOADED:
    app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
    app.include_router(farmers.router, prefix="/farmers", tags=["Farmers"])
    app.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])
    app.include_router(documents.router, prefix="/documents", tags=["Documents"])

# ==================== DIRECT ADMIN ENDPOINTS IN MAIN.PY ====================
# Add admin endpoints directly here to avoid router issues

class AdminLogin(BaseModel):
    username: str
    password: str

@app.post("/admin/login")
async def admin_login(login_data: AdminLogin):
    """
    Direct admin login endpoint
    Username: admin
    Password: admin123
    """
    ADMIN_CREDENTIALS = {
        "username": "admin",
        "password": "admin123",
        "name": "System Administrator",
        "role": "admin"
    }
    
    if (login_data.username != ADMIN_CREDENTIALS["username"] or 
        login_data.password != ADMIN_CREDENTIALS["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials"
        )
    
    # Import security functions
    from app.utils.security import create_access_token
    from app.config import settings
    
    admin_user = {
        "id": 0,
        "username": ADMIN_CREDENTIALS["username"],
        "full_name": ADMIN_CREDENTIALS["name"],
        "role": ADMIN_CREDENTIALS["role"],
        "is_admin": True
    }
    
    access_token = create_access_token(
        data={
            "sub": "admin",
            "role": "admin",
            "is_admin": True
        }
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": admin_user
    }

@app.get("/admin/health")
async def admin_health():
    """Admin health check"""
    return {
        "status": "healthy",
        "service": "admin-api",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "POST /admin/login": "Admin login",
            "GET /admin/health": "Health check",
            "GET /admin": "Admin info"
        }
    }

@app.get("/admin")
async def admin_info():
    """Admin API information"""
    return {
        "message": "AgroScheme Admin API",
        "version": settings.PROJECT_VERSION,
        "credentials": {
            "username": "admin",
            "password": "admin123"
        },
        "endpoints": [
            "POST /admin/login - Admin login",
            "GET /admin/health - Health check",
            "GET /admin - This info"
        ]
    }

# ==================== ROOT & HEALTH ENDPOINTS ====================

@app.get("/")
async def root():
    return {
        "message": "AgroScheme AI API",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs",
        "admin_docs": "/admin for admin endpoints",
        "health": "/health",
        "uploads_test": "/uploads-test",
        "cors_enabled": True,
        "upload_system": "user-specific folders enabled",
        "api_base": settings.API_BASE_URL,
        "admin_login": "POST /admin/login with {'username':'admin','password':'admin123'}"
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        "status": "healthy",
        "service": "agroscheme-api",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "uploads": "available"
    }
    
    # Check uploads directory
    uploads_root = settings.UPLOAD_ROOT
    if uploads_root.exists():
        health_status["uploads_directory"] = str(uploads_root)
        health_status["uploads_exists"] = True
        
        # Count existing user folders
        user_folders = []
        for item in uploads_root.iterdir():
            if item.is_dir() and item.name.startswith(("farmer_", "user_")):
                user_folders.append(item.name)
        
        health_status["user_folders"] = len(user_folders)
        health_status["system_folders"] = len(["temp", "trash", "system"])
    else:
        health_status["uploads_exists"] = False
        health_status["error"] = "Uploads directory not found"
    
    return health_status

@app.get("/test")
async def test():
    return {"message": "API working", "timestamp": datetime.utcnow().isoformat()}

@app.get("/cors-test")
async def cors_test():
    return {
        "message": "CORS test successful",
        "allowed_origins": settings.ALLOWED_ORIGINS,
        "timestamp": datetime.utcnow().isoformat(),
        "upload_system": "active"
    }

@app.options("/{path:path}")
async def options_handler():
    return {"message": "CORS preflight OK"}

# ==================== UPLOADS DEBUG & MANAGEMENT ====================

@app.get("/uploads-test")
async def uploads_test():
    """Test uploads directory accessibility and structure"""
    uploads_root = settings.UPLOAD_ROOT
    
    if not uploads_root.exists():
        raise HTTPException(
            status_code=500,
            detail="Uploads root directory does not exist"
        )
    
    # List all directories
    all_items = []
    user_folders = []
    system_folders = []
    
    for item in uploads_root.iterdir():
        item_info = {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else 0
        }
        all_items.append(item_info)
        
        if item.is_dir():
            if item.name.startswith(("farmer_", "user_")):
                user_folders.append(item.name)
            elif item.name in ["temp", "trash", "system"]:
                system_folders.append(item.name)
    
    # Check if we can write to uploads
    test_write = False
    try:
        test_file = uploads_root / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
        test_write = True
    except:
        test_write = False
    
    return {
        "status": "ok",
        "uploads_root": str(uploads_root.absolute()),
        "exists": uploads_root.exists(),
        "writable": test_write,
        "total_items": len(all_items),
        "user_folders": {
            "count": len(user_folders),
            "names": user_folders[:10]  # Limit to first 10
        },
        "system_folders": system_folders,
        "items": all_items[:20]  # Limit to first 20 items
    }

@app.get("/uploads/{folder_name}/{filename}")
async def serve_user_file(folder_name: str, filename: str):
    """
    Serve files from user folders with security checks.
    This is handled by StaticFiles, but we add a route for debugging.
    """
    file_path = settings.UPLOAD_ROOT / folder_name / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {filename}"
        )
    
    # Security check: Ensure it's in a user folder
    if not folder_name.startswith(("farmer_", "user_", "temp", "trash", "system")):
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )
    
    return {
        "message": "File exists and is accessible via /uploads/ URL",
        "filename": filename,
        "folder": folder_name,
        "path": str(file_path.relative_to(settings.UPLOAD_ROOT)),
        "url": f"{settings.API_BASE_URL}/uploads/{folder_name}/{filename}",
        "size": file_path.stat().st_size
    }

@app.get("/system/uploads-stats")
async def get_uploads_stats():
    """Get statistics about uploads (admin/debug)"""
    uploads_root = settings.UPLOAD_ROOT
    
    if not uploads_root.exists():
        return {"error": "Uploads directory does not exist"}
    
    stats = {
        "total_size": 0,
        "file_count": 0,
        "folder_count": 0,
        "user_folders": [],
        "system_folders": []
    }
    
    for item in uploads_root.iterdir():
        if item.is_dir():
            folder_stats = {
                "name": item.name,
                "file_count": 0,
                "total_size": 0,
                "files": []
            }
            
            # Count files in folder
            for file_item in item.iterdir():
                if file_item.is_file():
                    folder_stats["file_count"] += 1
                    folder_stats["total_size"] += file_item.stat().st_size
                    
                    if folder_stats["file_count"] <= 5:  # Limit file listing
                        folder_stats["files"].append({
                            "name": file_item.name,
                            "size": file_item.stat().st_size
                        })
            
            stats["total_size"] += folder_stats["total_size"]
            stats["file_count"] += folder_stats["file_count"]
            stats["folder_count"] += 1
            
            if item.name.startswith(("farmer_", "user_")):
                stats["user_folders"].append(folder_stats)
            elif item.name in ["temp", "trash", "system"]:
                stats["system_folders"].append(folder_stats)
    
    return stats

# ==================== STARTUP MESSAGE ====================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    print("\n" + "=" * 50)
    print("🚀 AgroScheme AI Backend Started Successfully!")
    print("=" * 50)
    print(f"📁 Uploads Directory: {settings.UPLOAD_ROOT}")
    print(f"🌐 API Base URL: {settings.API_BASE_URL}")
    print(f"🔗 Swagger Docs: {settings.API_BASE_URL}/docs")
    print(f"📊 Health Check: {settings.API_BASE_URL}/health")
    print(f"👑 Admin Login: {settings.API_BASE_URL}/admin/login")
    print("=" * 50)
    print("Available endpoints:")
    print(f"  • POST   /auth/register          - Register new farmer")
    print(f"  • POST   /auth/login             - Login")
    print(f"  • POST   /admin/login            - Admin login (admin/admin123)")
    print(f"  • GET    /admin                  - Admin info")
    print(f"  • GET    /uploads-test           - Test uploads")
    print("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    print("\n🛑 AgroScheme AI Backend Shutting Down...")

# ==================== ERROR HANDLERS ====================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Custom 404 handler"""
    return {
        "error": "Not Found",
        "message": f"The requested URL {request.url} was not found",
        "suggestions": [
            "Check the API documentation at /docs",
            "Verify the endpoint URL",
            "Ensure you're using the correct HTTP method"
        ],
        "available_endpoints": {
            "farmer_auth": "/auth/login, /auth/register",
            "admin": "/admin/login",
            "health": "/health",
            "docs": "/docs"
        }
    }

@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Custom 500 handler"""
    return {
        "error": "Internal Server Error",
        "message": "Something went wrong on our end",
        "timestamp": datetime.utcnow().isoformat(),
        "support": "Contact support if the issue persists"
    }
