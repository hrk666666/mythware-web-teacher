"""
极域屏幕广播模块

协议流程（基于公开逆向资料）：
1. 教师端通过TCP 7001向学生端发送"开始屏幕广播"握手命令
2. 学生端收到命令后IGMP加入组播组 225.2.2.11
3. 教师端截屏 -> JPEG编码 -> 通过UDP组播发送分片帧
4. 学生端从组播组接收JPEG帧 -> 解码 -> 全屏渲染

组播地址: 225.2.2.11 (V6版)
TCP端口: 7001
"""
import socket
import struct
import threading
import time
import io
import sys
from typing import Optional

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# 组播配置
BROADCAST_MULTICAST_GROUP = "225.2.2.11"
BROADCAST_TCP_PORT = 7001
BROADCAST_UDP_PORT = 7001

# JPEG分片大小（MTU=1500, IP头20, UDP头8, 留余量）
FRAGMENT_SIZE = 1400

# 帧头格式:
# 4字节魔数 "JPG1"
# 4字节总帧大小
# 4字节帧序号
# 4字节当前分片偏移
# 4字节当前分片大小
FRAME_HEADER_SIZE = 20
FRAME_MAGIC = b"JPG1"


class ScreenBroadcaster:
    """极域屏幕广播器"""

    def __init__(self):
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.teacher_ip = self._get_local_ip()
        self.fps = 5
        self.quality = 60
        self.target_students: list = []

        # 创建组播UDP socket
        self.mcast_sock = None
        self._init_mcast_socket()

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _init_mcast_socket(self):
        """初始化组播发送socket"""
        try:
            self.mcast_sock = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            )
            ttl = struct.pack('b', 16)
            self.mcast_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        except Exception:
            self.mcast_sock = None

    def send_handshake(self, student_ip: str) -> bool:
        """
        向学生端TCP 7001发送"开始屏幕广播"握手命令

        极域原生流程：教师端TCP建连后发送广播开始命令，
        学生端收到后IGMP join组播组。
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((student_ip, BROADCAST_TCP_PORT))

            # 构造广播开始命令包
            # 基于DMOC协议族的屏幕广播命令
            handshake = self._build_broadcast_start_packet()
            sock.send(handshake)

            # 等待学生端确认
            try:
                resp = sock.recv(1024)
            except socket.timeout:
                pass

            sock.close()
            return True
        except Exception:
            return False

    def _build_broadcast_start_packet(self) -> bytes:
        """
        构造屏幕广播开始命令包

        基于DMOC协议族：
        - 包头: "DMOC"
        - 命令类型: 屏幕广播开始
        - 携带组播地址信息
        """
        packet = bytearray(256)

        # DMOC包头
        packet[0:4] = b"DMOC"
        struct.pack_into("<H", packet, 4, 0x0001)

        # 屏幕广播开始命令码
        struct.pack_into("<H", packet, 6, 0x0500)

        # 会话ID
        import random
        for i in range(8, 16):
            packet[i] = random.randint(0, 0xFF)

        struct.pack_into("<H", packet, 16, 0x4E20)

        # 教师端IP
        packet[18:22] = socket.inet_aton(self.teacher_ip)

        # 组播地址信息（告诉学生端join哪个组播组）
        packet[22:26] = socket.inet_aton(BROADCAST_MULTICAST_GROUP)
        struct.pack_into("<H", packet, 26, BROADCAST_UDP_PORT)

        # 分辨率信息
        struct.pack_into("<H", packet, 28, 1920)  # 宽
        struct.pack_into("<H", packet, 30, 1080)  # 高

        # 标志位
        packet[32] = 0x01  # 开始广播标志

        return bytes(packet[:33])

    def send_frame_multicast(self, jpeg_data: bytes, frame_seq: int) -> int:
        """
        将JPEG帧分片发送到组播组

        帧格式:
        [魔数4B][总大小4B][帧序号4B][分片偏移4B][分片大小4B][JPEG数据]
        """
        if not self.mcast_sock:
            return 0

        total_size = len(jpeg_data)
        offset = 0
        fragment_count = 0

        while offset < total_size:
            chunk = jpeg_data[offset:offset + FRAGMENT_SIZE]

            # 构造帧头
            header = struct.pack(
                "<4sIIII",
                FRAME_MAGIC,
                total_size,
                frame_seq,
                offset,
                len(chunk)
            )

            packet = header + chunk

            try:
                self.mcast_sock.sendto(
                    packet,
                    (BROADCAST_MULTICAST_GROUP, BROADCAST_UDP_PORT)
                )
                fragment_count += 1
            except Exception:
                break

            offset += FRAGMENT_SIZE

        return fragment_count

    def capture_screen_jpeg(self) -> Optional[bytes]:
        """截屏并编码为JPEG"""
        if not HAS_PIL:
            return None
        try:
            img = ImageGrab.grab()
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=self.quality)
            return buf.getvalue()
        except Exception:
            return None

    def broadcast_loop(self):
        """广播主循环"""
        frame_seq = 0
        frame_interval = 1.0 / self.fps

        # 向所有学生端发送握手
        for ip in self.target_students:
            self.send_handshake(ip)
            time.sleep(0.1)

        while self.running:
            start_time = time.time()

            jpeg_data = self.capture_screen_jpeg()
            if jpeg_data:
                self.send_frame_multicast(jpeg_data, frame_seq)
                frame_seq += 1

            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def start(self, students: list, fps: int = 5, quality: int = 60) -> bool:
        """开始广播"""
        if self.running:
            return False

        self.target_students = students
        self.fps = fps
        self.quality = self.quality
        self.running = True

        self.thread = threading.Thread(target=self.broadcast_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """停止广播"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None

    def is_running(self) -> bool:
        return self.running


# 全局单例
_broadcaster: Optional[ScreenBroadcaster] = None


def get_broadcaster() -> ScreenBroadcaster:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = ScreenBroadcaster()
    return _broadcaster
