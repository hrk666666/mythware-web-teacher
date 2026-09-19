"""
极域电子教室协议层 - DMOC数据包构造
"""
import struct
import socket
import random
from typing import List, Optional


class PacketBuilder:
    """DMOC数据包构造器"""

    MAGIC = b"DMOC"

    CMD_EXEC = 0x036E
    CMD_REBOOT = 0x022A
    CMD_SHUTDOWN = 0x022A
    CMD_MESSAGE = 0x039E

    PORT_EXEC = 4705
    PORT_SHUTDOWN = 7005
    PORT_MESSAGE = 7006
    PORT_DISCOVER = 7000

    MULTICAST_DISCOVER = "224.50.50.42"
    MULTICAST_CONTROL = "225.2.2.111"
    MULTICAST_BROADCAST = "225.2.2.11"

    @staticmethod
    def _encode_wide_string(text: str, max_len: int = 200) -> List[int]:
        result = []
        for ch in text[:max_len]:
            code = ord(ch)
            if code > 0xFF:
                result.append(code & 0xFF)
                result.append((code >> 8) & 0xFF)
            else:
                result.append(code & 0xFF)
                result.append(0x00)
        return result

    @staticmethod
    def _random_session_id() -> bytes:
        return bytes([random.randint(0, 0xFF) for _ in range(8)])

    def build_exec_packet(self, target_ip: str, command: str, params: str = "") -> bytes:
        packet = bytearray(906)
        packet[0:4] = self.MAGIC
        struct.pack_into("<H", packet, 4, 0x0001)
        struct.pack_into("<H", packet, 6, self.CMD_EXEC)
        packet[8:16] = self._random_session_id()
        struct.pack_into("<H", packet, 16, 0x4E20)
        ip_bytes = socket.inet_aton(target_ip)
        packet[18:22] = ip_bytes
        struct.pack_into("<H", packet, 22, 0x0391)
        struct.pack_into("<H", packet, 24, 0x0391)
        struct.pack_into("<H", packet, 26, 0x0008)
        struct.pack_into("<I", packet, 28, 0x00000000)
        struct.pack_into("<H", packet, 32, 0x0005)
        struct.pack_into("<H", packet, 34, 0x0000)
        packet[36] = 0x01

        cmd_bytes = self._encode_wide_string(command)
        for i, b in enumerate(cmd_bytes):
            if 56 + i < 576:
                packet[56 + i] = b

        if params:
            param_bytes = self._encode_wide_string(params)
            for i, b in enumerate(param_bytes):
                if 578 + i < 896:
                    packet[578 + i] = b

        packet[896] = 0x01
        packet[900] = 0x01
        return bytes(packet)

    def build_message_packet(self, target_ip: str, message: str) -> bytes:
        packet = bytearray(906)
        packet[0:4] = self.MAGIC
        struct.pack_into("<H", packet, 4, 0x0001)
        struct.pack_into("<H", packet, 6, self.CMD_MESSAGE)
        packet[8:16] = self._random_session_id()
        struct.pack_into("<H", packet, 16, 0x4E20)
        ip_bytes = socket.inet_aton(target_ip)
        packet[18:22] = ip_bytes
        struct.pack_into("<H", packet, 22, 0x01D1)
        struct.pack_into("<H", packet, 24, 0x01D1)
        struct.pack_into("<H", packet, 26, 0x0002)
        struct.pack_into("<I", packet, 28, 0x00000000)

        msg_bytes = self._encode_wide_string(message, max_len=400)
        for i, b in enumerate(msg_bytes):
            if 56 + i < 896:
                packet[56 + i] = b
        return bytes(packet)

    def build_shutdown_packet(self, target_ip: str, reboot: bool = False) -> bytes:
        packet = bytearray(622)
        packet[0:4] = self.MAGIC
        struct.pack_into("<H", packet, 4, 0x0001)
        struct.pack_into("<H", packet, 6, self.CMD_SHUTDOWN)
        packet[8:16] = self._random_session_id()
        struct.pack_into("<H", packet, 16, 0x4E20)
        ip_bytes = socket.inet_aton(target_ip)
        packet[18:22] = ip_bytes
        struct.pack_into("<H", packet, 22, 0x021D)
        struct.pack_into("<H", packet, 24, 0x021D)
        struct.pack_into("<H", packet, 26, 0x0002)
        struct.pack_into("<I", packet, 28, 0x00000000)
        sub_cmd = 0x14 if reboot else 0x13
        struct.pack_into("<H", packet, 32, sub_cmd)
        struct.pack_into("<H", packet, 34, 0x000F)
        struct.pack_into("<H", packet, 36, 0x0010)
        packet[38] = 0x0F
        packet[40] = 0x01
        return bytes(packet)

    def build_heartbeat_packet(self) -> bytes:
        packet = bytearray(128)
        packet[0:4] = self.MAGIC
        struct.pack_into("<H", packet, 4, 0x0001)
        packet[8:16] = self._random_session_id()
        packet[20] = 0x01
        return bytes(packet)


def parse_ip_range(ip_str: str) -> List[str]:
    ips = []
    if "-" in ip_str:
        parts = ip_str.split("-")
        base = parts[0].split(".")
        start = int(base[3])
        end = int(parts[1])
        if end > 254:
            end = 254
        for i in range(start, end + 1):
            base[3] = str(i)
            ips.append(".".join(base))
    elif "/24" in ip_str:
        base = ip_str.replace("/24", "").split(".")
        for i in range(1, 255):
            base[3] = str(i)
            ips.append(".".join(base))
    else:
        ips.append(ip_str)
    return ips
