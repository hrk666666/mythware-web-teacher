"""
命令发送器
"""
import socket
import time
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from .protocol import PacketBuilder, parse_ip_range


class CommandSender:
    def __init__(self):
        self.builder = PacketBuilder()

    def _send_udp(self, ip: str, port: int, data: bytes, timeout: float = 1.0) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            sock.sendto(data, (ip, port))
            sock.close()
            return True
        except Exception:
            return False

    def exec_command(self, targets: List[str], command: str, params: str = "",
                     port: int = 4705, workers: int = 50) -> Dict:
        results = {"total": len(targets), "success": 0, "failed": 0, "details": []}

        def _do_exec(ip):
            pkt = self.builder.build_exec_packet(ip, command, params)
            ok = self._send_udp(ip, port, pkt)
            return ip, ok

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_do_exec, ip): ip for ip in targets}
            for f in as_completed(futures):
                ip, ok = f.result()
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({"ip": ip, "success": ok})

        return results

    def send_message(self, targets: List[str], message: str,
                     port: int = 7006, workers: int = 50) -> Dict:
        results = {"total": len(targets), "success": 0, "failed": 0, "details": []}

        def _do_msg(ip):
            pkt = self.builder.build_message_packet(ip, message)
            ok = self._send_udp(ip, port, pkt)
            return ip, ok

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_do_msg, ip): ip for ip in targets}
            for f in as_completed(futures):
                ip, ok = f.result()
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({"ip": ip, "success": ok})

        return results

    def shutdown(self, targets: List[str], reboot: bool = False,
                 port: int = 7005, workers: int = 50) -> Dict:
        results = {"total": len(targets), "success": 0, "failed": 0, "details": []}

        def _do_shutdown(ip):
            pkt = self.builder.build_shutdown_packet(ip, reboot=reboot)
            ok = self._send_udp(ip, port, pkt)
            return ip, ok

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_do_shutdown, ip): ip for ip in targets}
            for f in as_completed(futures):
                ip, ok = f.result()
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                results["details"].append({"ip": ip, "success": ok})

        return results
