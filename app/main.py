import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import engine, Base, SessionLocal
from app.models.db_models import TaskDB, ServerDB, NotificationDB, ConfigDB
from app.routers import (
    gemini_router,
    tasks_router,
    servers_router,
    notifications_router,
    config_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def seed_initial_data():
    """Seeds initial sample data if tables are empty"""
    db = SessionLocal()
    try:
        # Seed Tasks
        if db.query(TaskDB).count() == 0:
            logger.info("Seeding initial tasks...")
            db.add_all([
                TaskDB(
                    id="task_1",
                    title="Kiểm tra hệ thống Nginx",
                    description="Kiểm tra SSL certificate và log lỗi Nginx Reverse Proxy",
                    category="Server",
                    deadline="2026-07-22",
                    priority="High",
                    completed=False,
                    createdAt="2026-07-22"
                ),
                TaskDB(
                    id="task_2",
                    title="Cập nhật phiên bản Android APK",
                    description="Build ứng dụng Aegis Assistant APK với Capacitor",
                    category="Dev",
                    deadline="2026-07-25",
                    priority="Medium",
                    completed=True,
                    createdAt="2026-07-20"
                )
            ])

        # Seed Servers
        if db.query(ServerDB).count() == 0:
            logger.info("Seeding initial servers...")
            db.add_all([
                ServerDB(
                    id="srv_prod_01",
                    name="Production API Gateway",
                    ip="192.168.1.100",
                    status="up",
                    uptime=99.98,
                    latency=24.0,
                    cpuUsage=42.0,
                    memoryUsage=68.0,
                    diskUsage=75.0,
                    lastChecked="16:30:00"
                ),
                ServerDB(
                    id="srv_db_02",
                    name="Database Server 02",
                    ip="192.168.1.102",
                    status="up",
                    uptime=99.9,
                    latency=35.0,
                    cpuUsage=65.0,
                    memoryUsage=88.0,
                    diskUsage=82.0,
                    lastChecked="16:30:00"
                )
            ])

        # Seed Notifications
        if db.query(NotificationDB).count() == 0:
            logger.info("Seeding initial notifications...")
            db.add_all([
                NotificationDB(
                    id="notif_1",
                    title="Cảnh báo RAM Server-02",
                    description="Dung lượng RAM sử dụng vượt quá 85%",
                    category="server",
                    read=False,
                    timestamp="16:30"
                )
            ])

        # Seed Config
        if db.query(ConfigDB).count() == 0:
            logger.info("Seeding default config...")
            db.add(ConfigDB(
                id=1,
                name="Aegis",
                prompt="Bạn là Aegis, trợ lý ảo cá nhân đa năng...",
                avatarUrl="",
                themeColor="cyan",
                apiBaseUrl=f"http://localhost:{settings.port}"
            ))

        db.commit()
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Aegis Assistant Backend...")
    # Create DB tables
    Base.metadata.create_all(bind=engine)
    # Seed initial data
    seed_initial_data()
    yield
    logger.info("Shutting down Aegis Assistant Backend.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API & Gemini AI Agent Runtime for Aegis Assistant Mobile/Web App",
    lifespan=lifespan
)

# CORS Configuration for Mobile Capacitor WebView and Web client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(gemini_router)
app.include_router(tasks_router)
app.include_router(servers_router)
app.include_router(notifications_router)
app.include_router(config_router)


@app.get("/health", tags=["Health Check"])
def health_check():
    return {
        "status": "online",
        "service": settings.app_name,
        "version": settings.app_version,
        "model": settings.gemini_model,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
