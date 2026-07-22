from typing import Optional
from pydantic import BaseModel, Field


class ServerStatusBase(BaseModel):
    name: str
    ip: str
    status: str = "up"  # up, down, degraded
    uptime: float = 99.9
    latency: float = 20.0
    cpuUsage: float = 30.0
    memoryUsage: float = 50.0
    diskUsage: float = 60.0
    lastChecked: Optional[str] = ""


class ServerStatusCreate(ServerStatusBase):
    id: Optional[str] = None


class ServerStatusUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    status: Optional[str] = None
    uptime: Optional[float] = None
    latency: Optional[float] = None
    cpuUsage: Optional[float] = None
    memoryUsage: Optional[float] = None
    diskUsage: Optional[float] = None
    lastChecked: Optional[str] = None


class ServerStatusItem(ServerStatusBase):
    id: str

    class Config:
        from_attributes = True


class ServerPingResponse(BaseModel):
    id: str
    name: str
    ip: str
    status: str
    latency: float
    message: str
