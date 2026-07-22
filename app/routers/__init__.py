from app.routers.gemini import router as gemini_router
from app.routers.tasks import router as tasks_router
from app.routers.servers import router as servers_router
from app.routers.notifications import router as notifications_router
from app.routers.config import router as config_router

__all__ = ["gemini_router", "tasks_router", "servers_router", "notifications_router", "config_router"]
