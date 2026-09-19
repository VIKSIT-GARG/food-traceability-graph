"""Entrypoint for the Food Traceability Graph Web Application.

Exports the FastAPI application defined in api.main.
Supports running directly or with an ASGI server:
    uvicorn web_app:app --reload
    python web_app.py
"""
import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.main import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="0.0.0.0", port=8000, reload=True)
