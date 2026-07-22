import asyncio
import time
import socket
from typing import Dict, Any, List


async def ping_server_tool(ip_or_host: str) -> Dict[str, Any]:
    """
    Executes a socket latency test / host check on given IP or hostname.
    """
    # Clean host string
    host = ip_or_host.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
    
    start_time = time.time()
    latency_ms = 0.0
    status = "down"
    message = ""

    try:
        # Try socket connect on port 80 or 443 or 22
        loop = asyncio.get_event_loop()
        def _connect():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            try:
                s.connect((host, 80))
                return True
            except Exception:
                try:
                    s.connect((host, 443))
                    return True
                except Exception:
                    return False
            finally:
                s.close()

        success = await loop.run_in_executor(None, _connect)
        latency_ms = round((time.time() - start_time) * 1000, 2)

        if success:
            if latency_ms > 200:
                status = "degraded"
                message = f"Máy chủ {host} hoạt động nhưng độ trễ cao ({latency_ms}ms)."
            else:
                status = "up"
                message = f"Máy chủ {host} phản hồi tốt ({latency_ms}ms)."
        else:
            # Fallback ping via socket lookup
            try:
                await loop.run_in_executor(None, socket.gethostbyname, host)
                latency_ms = round((time.time() - start_time) * 1000, 2)
                status = "up"
                message = f"Máy chủ {host} đã phân giải được IP ({latency_ms}ms)."
            except Exception:
                status = "down"
                latency_ms = 0.0
                message = f"Không thể kết nối đến máy chủ {host}."
    except Exception as e:
        status = "down"
        latency_ms = 0.0
        message = f"Lỗi ping máy chủ {host}: {str(e)}"

    return {
        "ip": host,
        "status": status,
        "latency": latency_ms,
        "message": message
    }


def analyze_task_health(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("completed"))
    pending = total - completed
    high_priority = [t for t in tasks if t.get("priority") == "High" and not t.get("completed")]
    
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "high_priority_pending_count": len(high_priority),
        "high_priority_tasks": high_priority
    }


def analyze_server_health(servers: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(servers)
    down_servers = [s for s in servers if s.get("status") == "down"]
    degraded_servers = [s for s in servers if s.get("status") == "degraded" or (s.get("latency", 0) > 200)]
    high_ram_servers = [s for s in servers if s.get("memoryUsage", 0) > 85]
    high_cpu_servers = [s for s in servers if s.get("cpuUsage", 0) > 85]

    return {
        "total": total,
        "down_count": len(down_servers),
        "down_servers": down_servers,
        "degraded_count": len(degraded_servers),
        "degraded_servers": degraded_servers,
        "high_ram_servers": high_ram_servers,
        "high_cpu_servers": high_cpu_servers
    }
