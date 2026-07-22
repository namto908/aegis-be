#!/usr/bin/env python3
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"🚀 Starting Aegis Assistant Backend on http://{settings.host}:{settings.port}")
    print(f"📖 Swagger API Docs available at http://localhost:{settings.port}/docs")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
