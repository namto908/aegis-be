import time
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.db_models import ServerDB
from app.schemas.server import ServerStatusItem, ServerStatusCreate, ServerStatusUpdate, ServerPingResponse
from app.agent.tools import ping_server_tool

router = APIRouter(prefix="/api/servers", tags=["Servers"])


class PingPayload(BaseModel):
    id: Optional[str] = None
    ip: str
    name: Optional[str] = ""


@router.get("", response_model=List[ServerStatusItem])
def get_all_servers(db: Session = Depends(get_db)):
    """GET /api/servers - Retrieve list of all servers"""
    servers = db.query(ServerDB).all()
    return servers


@router.post("", response_model=ServerStatusItem, status_code=status.HTTP_201_CREATED)
def create_server(server_in: ServerStatusCreate, db: Session = Depends(get_db)):
    """POST /api/servers - Add a server to monitor"""
    server_id = server_in.id or f"srv_{int(time.time() * 1000)}"
    last_checked = server_in.lastChecked or time.strftime("%H:%M:%S")

    db_server = ServerDB(
        id=server_id,
        name=server_in.name,
        ip=server_in.ip,
        status=server_in.status or "up",
        uptime=server_in.uptime,
        latency=server_in.latency,
        cpuUsage=server_in.cpuUsage,
        memoryUsage=server_in.memoryUsage,
        diskUsage=server_in.diskUsage,
        lastChecked=last_checked
    )
    db.add(db_server)
    db.commit()
    db.refresh(db_server)
    return db_server


@router.put("/{server_id}", response_model=ServerStatusItem)
def update_server(server_id: str, server_in: ServerStatusUpdate, db: Session = Depends(get_db)):
    """PUT /api/servers/{server_id} - Update server status / details"""
    db_server = db.query(ServerDB).filter(ServerDB.id == server_id).first()
    if not db_server:
        raise HTTPException(status_code=404, detail=f"Server with ID {server_id} not found")

    update_data = server_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(db_server, field, val)

    db.commit()
    db.refresh(db_server)
    return db_server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(server_id: str, db: Session = Depends(get_db)):
    """DELETE /api/servers/{server_id} - Delete server"""
    db_server = db.query(ServerDB).filter(ServerDB.id == server_id).first()
    if not db_server:
        raise HTTPException(status_code=404, detail=f"Server with ID {server_id} not found")

    db.delete(db_server)
    db.commit()
    return None


@router.post("/ping", response_model=ServerPingResponse)
async def ping_server(payload: PingPayload, db: Session = Depends(get_db)):
    """POST /api/servers/ping - Ping a server IP/Hostname and update status"""
    res = await ping_server_tool(payload.ip)

    now_time = time.strftime("%H:%M:%S")

    # If server_id is provided, update DB
    if payload.id:
        db_server = db.query(ServerDB).filter(ServerDB.id == payload.id).first()
        if db_server:
            db_server.status = res["status"]
            db_server.latency = res["latency"]
            db_server.lastChecked = now_time
            db.commit()

    return ServerPingResponse(
        id=payload.id or "ping_target",
        name=payload.name or payload.ip,
        ip=payload.ip,
        status=res["status"],
        latency=res["latency"],
        message=res["message"]
    )
