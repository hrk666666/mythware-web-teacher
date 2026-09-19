"""
学生端发现模块
"""
import socket
import struct
import threading
import time
from typing import List, Dict, Optional
from datetime import datetime

from .protocol import PacketBuilder, parse_ip_range


class StudentNode:
    def __init__(self, ip: str, port: int = 4705):
        self.ip = ip
        self.port = port
        self.hostname: Optional[str] = None
        self.last_seen: Optional[datetime] = None
        self.online: bool = True
        self.status: str = "unknown"
        self.checked: bool = False

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "port": self.port,
            "hostname": self.hostname or "未知",
            "last_seen": self.last_seen.strftime("%H:%M:%S") if self.last_seen else "-",
            "online": self.online,
            "status": self.status,
            "checked": self.checked,
        }


class StudentDiscovery:
    def __init__(self):
        self.students: Dict[str, StudentNode] = {}
        self._lock = threading.Lock()
        self.builder = PacketBuilder()

    def scan_network(self, subnet: str, timeout: float = 0.2) -> List[StudentNode]:
        ips = parse_ip_range(subnet)
        found = []

        for ip in ips:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)
                probe = self.builder.build_heartbeat_packet()
                sock.sendto(probe, (ip, 4705))
                data, addr = sock.recvfrom(1024)
                if data:
                    with self._lock:
                        if ip not in self.students:
                            node = StudentNode(ip)
                            node.last_seen = datetime.now()
                            node.online = True
                            node.status = "online"
                            node.checked = True
                            self.students[ip] = node
                            found.append(node)
                        else:
                            self.students[ip].online = True
                            self.students[ip].last_seen = datetime.now()
                            self.students[ip].status = "online"
                            self.students[ip].checked = True
                sock.close()
            except socket.timeout:
                pass
            except Exception:
                pass

        return found

    def quick_check(self, ip: str, port: int = 4705, timeout: float = 0.3) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            probe = self.builder.build_heartbeat_packet()
            sock.sendto(probe, (ip, port))
            data, addr = sock.recvfrom(1024)
            sock.close()
            return True
        except Exception:
            return False

    def get_all(self) -> List[StudentNode]:
        with self._lock:
            return list(self.students.values())

    def get_online(self) -> List[StudentNode]:
        with self._lock:
            return [s for s in self.students.values() if s.online]
