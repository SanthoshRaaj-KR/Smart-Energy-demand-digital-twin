"""
backend/server.py
=================
FastAPI entrypoint and server startup.

All routes defined in routes.py.

Run:
    uvicorn server:app --reload --port 8000
"""

from routes import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
