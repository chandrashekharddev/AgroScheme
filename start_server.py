# start_server.py
if __name__ == "__main__":
    import subprocess
    import sys
    
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "app.main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000", 
        "--reload"
    ])