# render_start.py
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )