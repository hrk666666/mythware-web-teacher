#!/usr/bin/env python3
"""
极域学生端代理 - 屏幕监控/广播代理
运行在学生机上，配合Web教师端使用

功能：
- 定时截屏并上传到教师端（屏幕监控）
- 从教师端拉取广播帧并全屏显示（屏幕广播）

依赖: pip install pillow requests
"""
import io
import sys
import time
import threading
import argparse
import requests
from PIL import ImageGrab, ImageTk
import tkinter as tk


class ScreenAgent:
    def __init__(self, teacher_url: str, interval: float = 2.0):
        self.teacher_url = teacher_url.rstrip("/")
        self.interval = interval
        self.running = True
        self.hostname = socket.gethostname()
        self.ip = self._get_local_ip()

        # 广播窗口
        self.broadcast_window = None
        self.broadcast_label = None

    def _get_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def upload_screenshot(self):
        """截屏并上传到教师端"""
        while self.running:
            try:
                # 截屏
                img = ImageGrab.grab()
                # 缩小尺寸减少流量
                img.thumbnail((800, 600))
                # 转JPEG
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60)
                b64 = base64.b64encode(buf.getvalue()).decode()

                # 上传
                requests.post(
                    f"{self.teacher_url}/api/screen/upload",
                    json={
                        "ip": self.ip,
                        "hostname": self.hostname,
                        "screenshot": b64,
                    },
                    timeout=5,
                )
            except Exception as e:
                pass
            time.sleep(self.interval)

    def listen_broadcast(self):
        """监听广播状态并显示"""
        while self.running:
            try:
                resp = requests.get(f"{self.teacher_url}/api/broadcast/status", timeout=3)
                data = resp.json()

                if data.get("active"):
                    # 获取最新帧
                    resp2 = requests.get(f"{self.teacher_url}/api/broadcast/frame/latest", timeout=3)
                    frame_data = resp2.json()
                    if frame_data.get("success") and frame_data.get("frame"):
                        self._show_broadcast_frame(frame_data["frame"])
                else:
                    self._hide_broadcast()

            except Exception:
                pass
            time.sleep(0.5)

    def _show_broadcast_frame(self, b64data: str):
        """显示广播帧"""
        try:
            img_data = base64.b64decode(b64data)
            img = Image.open(io.BytesIO(img_data))

            if not self.broadcast_window:
                # 创建全屏窗口
                self.broadcast_window = tk.Toplevel()
                self.broadcast_window.attributes("-fullscreen", True)
                self.broadcast_window.attributes("-topmost", True)
                self.broadcast_window.configure(background="black")
                self.broadcast_label = tk.Label(self.broadcast_window)
                self.broadcast_label.pack(fill=tk.BOTH, expand=True)

            # 调整大小适应屏幕
            screen_w = self.broadcast_window.winfo_screenwidth()
            screen_h = self.broadcast_window.winfo_screenheight()
            img = img.resize((screen_w, screen_h), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self.broadcast_label.config(image=photo)
            self.broadcast_label.image = photo
            self.broadcast_window.update()

        except Exception:
            pass

    def _hide_broadcast(self):
        """隐藏广播窗口"""
        if self.broadcast_window:
            try:
                self.broadcast_window.destroy()
            except Exception:
                pass
            self.broadcast_window = None
            self.broadcast_label = None

    def start(self):
        """启动代理"""
        print(f"[*] 学生代理启动")
        print(f"[*] 本机IP: {self.ip}")
        print(f"[*] 教师端: {self.teacher_url}")
        print(f"[*] 截屏间隔: {self.interval}秒")
        print()

        # 启动上传线程
        t_upload = threading.Thread(target=self.upload_screenshot, daemon=True)
        t_upload.start()

        # 启动广播监听线程
        t_broadcast = threading.Thread(target=self.listen_broadcast, daemon=True)
        t_broadcast.start()

        # 主循环（tkinter）
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.mainloop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        print("\n[*] 代理已停止")


import socket
import base64


def main():
    parser = argparse.ArgumentParser(description="极域学生端代理")
    parser.add_argument("--teacher", default="http://192.168.1.100:5000",
                        help="教师端地址")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="截屏间隔（秒）")
    args = parser.parse_args()

    agent = ScreenAgent(args.teacher, args.interval)
    try:
        agent.start()
    except KeyboardInterrupt:
        agent.stop()


if __name__ == "__main__":
    main()
