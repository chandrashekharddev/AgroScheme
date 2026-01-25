#!/usr/bin/env python3
import os
import uvicorn

if __name__ == "__main__":
    # Create uploads directory if it doesn't exist
    uploads_dir = "uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        print(f"Created uploads directory: {uploads_dir}")
    
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get("PORT", 10000))
    
    # Run the FastAPI app
    print(f"Starting server on port {port}...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False  # Set to False for production
    )
